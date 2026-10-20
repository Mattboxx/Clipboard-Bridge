package io.github.mattbox03.clipboardbridge

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import okio.BufferedSink
import okio.source
import org.json.JSONObject
import java.io.File
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

class ApiClient internal constructor(
    private val readSettings: () -> BridgeSettings,
    private val rememberSent: (String, BridgeSettings) -> Unit,
    private val client: OkHttpClient,
) {
    constructor(
        config: AppConfig,
        client: OkHttpClient = defaultHttpClient(),
    ) : this(config::load, config::setLastSeenId, client)

    // An unsaved Settings probe must not read or modify the active connection.
    internal constructor(settings: BridgeSettings) : this({ settings }, { _, _ -> }, defaultHttpClient())

    private fun request(path: String, settings: BridgeSettings): Request.Builder {
        settings.requireCurrentConnection(readSettings())
        require(!settings.accountMode || settings.username.isNotBlank()) {
            "Enter an account username or select Shared space."
        }
        val base = AppConfig.normalizeServerUrl(settings.serverUrl)
        val builder = Request.Builder().url(buildRequestUrl(base, path, settings))
        if (settings.accountMode && settings.username.isNotBlank() &&
            canUseCredentialHeaders(settings.username.trim(), settings.password)) {
            builder.header("X-Clipboard-User", settings.username.trim())
            builder.header("X-Clipboard-Password", settings.password)
        } else if (!settings.accountMode && settings.token.isNotBlank() &&
            canUseCredentialHeaders(settings.token.trim())) {
            builder.header("X-Auth-Token", settings.token.trim())
        }
        return builder
    }

    fun testConnection(settings: BridgeSettings = readSettings()): OperationResult<String> = runCatching {
        require(settings.serverUrl.isNotBlank()) { "Enter a server address." }
        client.newCall(request("/clipboard/history?limit=1", settings).get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                error(httpError(response.code, payload))
            }
            require(JSONObject(payload).optJSONArray("items") != null) {
                "The server did not return clipboard history. Check its address."
            }
            settings.requireCurrentConnection(readSettings())
            "Connected"
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun history(limit: Int = 200, settings: BridgeSettings = readSettings()): OperationResult<List<HistoryItem>> = runCatching {
        client.newCall(request("/clipboard/history?limit=$limit", settings).get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            val root = JSONObject(payload)
            val items = root.optJSONArray("items")
                ?: error("The server did not return clipboard history. Check its address.")
            buildList {
                for (index in 0 until items.length()) {
                    val item = items.getJSONObject(index)
                    add(
                        HistoryItem(
                            id = item.optString("id"),
                            type = item.optString("type", "file"),
                            filename = item.stringOrNull("filename"),
                            mime = item.stringOrNull("mime"),
                            timestamp = item.stringOrNull("timestamp"),
                            preview = item.stringOrNull("preview"),
                            fileCount = item.optInt("file_count", 0),
                            files = item.optJSONArray("files")?.let { files ->
                                buildList {
                                    for (fileIndex in 0 until files.length()) {
                                        val file = files.getJSONObject(fileIndex)
                                        add(
                                            BundleFile(
                                                index = file.optInt("index", fileIndex),
                                                filename = file.stringOrNull("filename") ?: "file-${fileIndex + 1}",
                                                mime = file.stringOrNull("mime") ?: "application/octet-stream",
                                                size = file.optLong("size", 0),
                                            ),
                                        )
                                    }
                                }
                            } ?: emptyList(),
                        ),
                    )
                }
            }.also { settings.requireCurrentConnection(readSettings()) }
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun uploadText(text: String, settings: BridgeSettings = readSettings()): OperationResult<String> {
        val body = text.toRequestBody("text/plain; charset=utf-8".toMediaTypeOrNull())
        return upload(body, null, settings)
    }

    fun uploadUri(
        resolver: ContentResolver,
        uri: Uri,
        filename: String = resolver.displayName(uri),
        mime: String = resolver.getType(uri) ?: "application/octet-stream",
        settings: BridgeSettings = readSettings(),
    ): OperationResult<String> = uploadUris(
        resolver,
        listOf(OutgoingClipboard.Content(uri, filename, mime)),
        settings,
    )

    fun uploadUris(
        resolver: ContentResolver,
        items: List<OutgoingClipboard.Content>,
        settings: BridgeSettings = readSettings(),
    ): OperationResult<String> {
        return runCatching {
            require(items.isNotEmpty()) { "No files were selected." }
            val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
            items.forEach { item ->
                multipart.addFormDataPart(
                    "files",
                    item.filename,
                    uriRequestBody(resolver, item.uri, item.mime),
                )
            }
            client.newCall(request("/clipboard", settings).post(multipart.build()).build()).execute().use { response ->
                val payload = response.body?.string().orEmpty()
                if (!response.isSuccessful) error(httpError(response.code, payload))
                acknowledgeUpload(payload, settings)
            }
        }.fold(
            onSuccess = { OperationResult.Success(it) },
            onFailure = { OperationResult.Error(it.userMessage()) },
        )
    }

    private fun uriRequestBody(
        resolver: ContentResolver,
        uri: Uri,
        mime: String,
    ): RequestBody {
        val length = resolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L
        return object : RequestBody() {
            override fun contentType() = mime.toMediaTypeOrNull()
            override fun contentLength() = length
            override fun writeTo(sink: BufferedSink) {
                resolver.openInputStream(uri)?.use { input -> sink.writeAll(input.source()) }
                    ?: error("The selected file cannot be opened.")
            }
        }
    }

    private fun upload(body: RequestBody, filename: String?, settings: BridgeSettings): OperationResult<String> = runCatching {
        val builder = request("/clipboard", settings)
            .post(body)
        if (!filename.isNullOrBlank()) {
            builder.header("X-Clipboard-Filename", filename)
        }
        client.newCall(builder.build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            acknowledgeUpload(payload, settings)
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun downloadLatest(cacheDir: File, settings: BridgeSettings = readSettings()): OperationResult<ReceivedClipboard> =
        download("/clipboard/latest/raw", cacheDir, settings)

    private fun acknowledgeUpload(payload: String, settings: BridgeSettings): String {
        val id = JSONObject(payload).opt("id") as? String
        require(!id.isNullOrBlank()) { "The server did not confirm the saved clipboard item." }
        settings.requireCurrentConnection(readSettings())
        rememberSent(id, settings)
        return id
    }

    fun downloadItem(id: String, cacheDir: File, settings: BridgeSettings = readSettings()): OperationResult<ReceivedClipboard> =
        download("/clipboard/item/$id/raw", cacheDir, settings)

    fun deleteItem(id: String, settings: BridgeSettings = readSettings()): OperationResult<String> = runCatching {
        client.newCall(request("/clipboard/item/$id", settings).delete().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            settings.requireCurrentConnection(readSettings())
            id
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    private fun download(path: String, cacheDir: File, settings: BridgeSettings): OperationResult<ReceivedClipboard> = runCatching {
        client.newCall(request(path, settings).get().build()).execute().use { response ->
            if (!response.isSuccessful) {
                error(httpError(response.code, response.body?.string().orEmpty()))
            }
            val type = response.header("X-Clipboard-Type").orEmpty()
            val id = response.header("X-Clipboard-Id").orEmpty()
            val mime = response.body?.contentType()?.toString()
                ?.substringBefore(';')
                ?: "application/octet-stream"
            val received = if (type == "bundle") {
                downloadBundle(id, cacheDir, settings)
            } else if (type == "text" || (type.isBlank() && mime.startsWith("text/"))) {
                ReceivedClipboard.Text(id, response.body?.string().orEmpty())
            } else {
                val encodedName = response.header("X-Clipboard-Filename").orEmpty()
                val filename = sanitizeFilename(
                    URLDecoder.decode(encodedName, StandardCharsets.UTF_8.name())
                        .ifBlank { "clipboard-file" },
                )
                val file = cacheFile(response.body, cacheDir)
                ReceivedClipboard.FileItem(id, file, filename, mime)
            }
            try {
                settings.requireCurrentConnection(readSettings())
                received
            } catch (error: Throwable) {
                received.discardCachedFiles()
                throw error
            }
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    private fun downloadBundle(id: String, cacheDir: File, settings: BridgeSettings): ReceivedClipboard.FileGroup {
        require(id.isNotBlank()) { "The server did not identify the file group." }
        val metadata = client.newCall(request("/clipboard/item/$id", settings).get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            JSONObject(payload)
        }
        val files = metadata.optJSONArray("files") ?: error("The file group is empty.")
        val downloaded = mutableListOf<ReceivedClipboard.FileItem>()
        try {
            for (index in 0 until files.length()) {
                val member = files.getJSONObject(index)
                val memberIndex = member.optInt("index", index)
                val filename = sanitizeFilename(
                    member.stringOrNull("filename") ?: "file-${index + 1}",
                )
                val mime = member.stringOrNull("mime") ?: "application/octet-stream"
                val file = client.newCall(
                    request("/clipboard/item/$id/file/$memberIndex/raw", settings).get().build(),
                ).execute().use { response ->
                    if (!response.isSuccessful) {
                        error(httpError(response.code, response.body?.string().orEmpty()))
                    }
                    cacheFile(response.body, cacheDir)
                }
                downloaded.add(ReceivedClipboard.FileItem(id, file, filename, mime))
            }
            require(downloaded.isNotEmpty()) { "The file group is empty." }
            return ReceivedClipboard.FileGroup(id, downloaded)
        } catch (error: Throwable) {
            downloaded.forEach { runCatching { it.file.delete() } }
            throw error
        }
    }

    private fun cacheFile(body: ResponseBody?, cacheDir: File): File {
        requireNotNull(body) { "The server returned an empty response." }
        val directory = File(cacheDir, "received").apply { mkdirs() }
        val file = File.createTempFile("clipboard-", ".tmp", directory)
        try {
            body.byteStream().use { input ->
                file.outputStream().use { output -> input.copyTo(output) }
            }
            return file
        } catch (error: Throwable) {
            runCatching { file.delete() }
            throw error
        }
    }

    private fun httpError(code: Int, responseBody: String = ""): String {
        val base = when (code) {
            401 -> "Authentication failed. Check the token or account."
            404 -> "No clipboard item is available."
            413 -> "The file exceeds the server upload limit."
            else -> "Server error ($code)."
        }
        val jsonDetail = runCatching {
            JSONObject(responseBody).optString("error")
                .ifBlank { JSONObject(responseBody).optString("message") }
        }.getOrNull()
        val detail = (jsonDetail ?: responseBody)
            .replace(Regex("<[^>]+>"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
            .take(180)
        return if (detail.isBlank() || base.contains(detail, ignoreCase = true)) {
            base
        } else {
            "$base $detail"
        }
    }
}

private fun defaultHttpClient(): OkHttpClient = OkHttpClient.Builder()
    .connectTimeout(6, TimeUnit.SECONDS)
    .readTimeout(30, TimeUnit.SECONDS)
    .writeTimeout(60, TimeUnit.SECONDS)
    .build()

internal fun canUseCredentialHeaders(vararg values: String): Boolean =
    values.all { value -> value == value.trim() && value.all { it in ' '..'~' } }

internal fun buildRequestUrl(
    base: String,
    path: String,
    settings: BridgeSettings,
) = "$base$path".toHttpUrl().newBuilder().apply {
    if (settings.accountMode && settings.username.isNotBlank()) {
        addQueryParameter("user", settings.username.trim())
        addQueryParameter("password", settings.password)
    } else if (settings.token.isNotBlank() && !canUseCredentialHeaders(settings.token.trim())) {
        addQueryParameter("token", settings.token.trim())
    }
}.build()

private fun JSONObject.stringOrNull(key: String): String? {
    if (!has(key) || isNull(key)) return null
    return optString(key).trim().takeIf { it.isNotEmpty() && it != "null" }
}

private fun Throwable.userMessage(): String {
    val value = message.orEmpty()
    return when {
        value.contains("CLEARTEXT", ignoreCase = true) ->
            "Android blocked the HTTP connection."
        value.contains("Failed to connect", ignoreCase = true) ->
            "Server unreachable. Check its address and the network."
        value.contains("timeout", ignoreCase = true) ->
            "The server did not respond in time."
        value.isNotBlank() -> redactCredentialUrls(value)
        else -> "Unexpected communication error."
    }
}

internal fun redactCredentialUrls(message: String): String =
    Regex("(?i)([?&](?:user|password|token)=)[^&#\\s\"']*").replace(message) {
        "${it.groupValues[1]}[redacted]"
    }

fun ContentResolver.displayName(uri: Uri): String {
    query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (column >= 0 && cursor.moveToFirst()) {
            return sanitizeFilename(cursor.getString(column))
        }
    }
    return sanitizeFilename(uri.lastPathSegment ?: "clipboard-file")
}

fun sanitizeFilename(value: String): String {
    val cleaned = value.replace(Regex("[\\\\/:*?\"<>|\\u0000-\\u001F]"), "_").trim()
    return cleaned.take(180).ifBlank { "clipboard-file" }
}
