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
import okio.BufferedSink
import okio.source
import org.json.JSONObject
import java.io.File
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

class ApiClient(
    private val config: AppConfig,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build(),
) {
    private fun request(path: String): Request.Builder {
        val settings = config.load()
        val base = AppConfig.normalizeServerUrl(settings.serverUrl)
        val builder = Request.Builder().url(buildRequestUrl(base, path, settings))
        if (settings.accountMode && settings.username.isNotBlank()) {
            builder.header("X-Clipboard-User", settings.username.trim())
            builder.header("X-Clipboard-Password", settings.password)
        } else if (settings.token.isNotBlank()) {
            builder.header("X-Auth-Token", settings.token.trim())
        }
        return builder
    }

    fun testConnection(): OperationResult<String> = runCatching {
        require(config.load().serverUrl.isNotBlank()) { "Enter a server address." }
        client.newCall(request("/clipboard/history?limit=1").get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                error(httpError(response.code, payload))
            }
            "Connected"
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun history(limit: Int = 200): OperationResult<List<HistoryItem>> = runCatching {
        client.newCall(request("/clipboard/history?limit=$limit").get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            val root = JSONObject(payload)
            val items = root.optJSONArray("items") ?: return@use emptyList()
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
            }
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun uploadText(text: String): OperationResult<String> {
        val body = text.toRequestBody("text/plain; charset=utf-8".toMediaTypeOrNull())
        return upload(body, null)
    }

    fun uploadUri(
        resolver: ContentResolver,
        uri: Uri,
        filename: String = resolver.displayName(uri),
        mime: String = resolver.getType(uri) ?: "application/octet-stream",
    ): OperationResult<String> {
        val body = uriRequestBody(resolver, uri, mime)
        return upload(body, filename)
    }

    fun uploadUris(
        resolver: ContentResolver,
        items: List<OutgoingClipboard.Content>,
    ): OperationResult<String> {
        if (items.size == 1) {
            val item = items.first()
            return uploadUri(resolver, item.uri, item.filename, item.mime)
        }
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
            client.newCall(request("/clipboard").post(multipart.build()).build()).execute().use { response ->
                val payload = response.body?.string().orEmpty()
                if (!response.isSuccessful) error(httpError(response.code, payload))
                JSONObject(payload).optString("id").also { id ->
                    if (id.isNotBlank()) config.setLastSeenId(id)
                }
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

    private fun upload(body: RequestBody, filename: String?): OperationResult<String> = runCatching {
        val builder = request("/clipboard")
            .post(body)
        if (!filename.isNullOrBlank()) {
            builder.header("X-Clipboard-Filename", filename)
        }
        client.newCall(builder.build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            val id = JSONObject(payload).optString("id")
            if (id.isNotBlank()) config.setLastSeenId(id)
            id
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    fun downloadLatest(cacheDir: File): OperationResult<ReceivedClipboard> =
        download("/clipboard/latest/raw", cacheDir)

    fun downloadItem(id: String, cacheDir: File): OperationResult<ReceivedClipboard> =
        download("/clipboard/item/$id/raw", cacheDir)

    fun deleteItem(id: String): OperationResult<String> = runCatching {
        client.newCall(request("/clipboard/item/$id").delete().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            id
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    private fun download(path: String, cacheDir: File): OperationResult<ReceivedClipboard> = runCatching {
        client.newCall(request(path).get().build()).execute().use { response ->
            if (!response.isSuccessful) {
                error(httpError(response.code, response.body?.string().orEmpty()))
            }
            val type = response.header("X-Clipboard-Type").orEmpty()
            val id = response.header("X-Clipboard-Id").orEmpty()
            val mime = response.body?.contentType()?.toString()
                ?.substringBefore(';')
                ?: "application/octet-stream"
            if (type == "bundle") {
                downloadBundle(id, cacheDir)
            } else if (type == "text" || mime.startsWith("text/")) {
                ReceivedClipboard.Text(id, response.body?.string().orEmpty())
            } else {
                val encodedName = response.header("X-Clipboard-Filename").orEmpty()
                val filename = sanitizeFilename(
                    URLDecoder.decode(encodedName, StandardCharsets.UTF_8.name())
                        .ifBlank { "clipboard-file" },
                )
                val directory = File(cacheDir, "received").apply { mkdirs() }
                val file = File(directory, "${System.nanoTime()}-$filename")
                response.body?.byteStream()?.use { input ->
                    file.outputStream().use { output -> input.copyTo(output) }
                } ?: error("The server returned an empty response.")
                ReceivedClipboard.FileItem(id, file, filename, mime)
            }
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.userMessage()) },
    )

    private fun downloadBundle(id: String, cacheDir: File): ReceivedClipboard.FileGroup {
        require(id.isNotBlank()) { "The server did not identify the file group." }
        val metadata = client.newCall(request("/clipboard/item/$id").get().build()).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) error(httpError(response.code, payload))
            JSONObject(payload)
        }
        val files = metadata.optJSONArray("files") ?: error("The file group is empty.")
        val directory = File(cacheDir, "received").apply { mkdirs() }
        val downloaded = buildList {
            for (index in 0 until files.length()) {
                val member = files.getJSONObject(index)
                val memberIndex = member.optInt("index", index)
                val filename = sanitizeFilename(
                    member.stringOrNull("filename") ?: "file-${index + 1}",
                )
                val mime = member.stringOrNull("mime") ?: "application/octet-stream"
                val file = File(directory, "${System.nanoTime()}-$filename")
                client.newCall(
                    request("/clipboard/item/$id/file/$memberIndex/raw").get().build(),
                ).execute().use { response ->
                    if (!response.isSuccessful) {
                        error(httpError(response.code, response.body?.string().orEmpty()))
                    }
                    response.body?.byteStream()?.use { input ->
                        file.outputStream().use { output -> input.copyTo(output) }
                    } ?: error("The server returned an empty file.")
                }
                add(ReceivedClipboard.FileItem(id, file, filename, mime))
            }
        }
        require(downloaded.isNotEmpty()) { "The file group is empty." }
        return ReceivedClipboard.FileGroup(id, downloaded)
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

internal fun buildRequestUrl(
    base: String,
    path: String,
    settings: BridgeSettings,
) = "$base$path".toHttpUrl().newBuilder().apply {
    if (settings.accountMode && settings.username.isNotBlank()) {
        addQueryParameter("user", settings.username.trim())
        addQueryParameter("password", settings.password)
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
        value.isNotBlank() -> value
        else -> "Unexpected communication error."
    }
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
