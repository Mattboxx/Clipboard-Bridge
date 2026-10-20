package io.github.mattbox03.clipboardbridge

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.core.content.IntentCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class BridgeRepository(private val context: Context) {
    private val config = AppConfig(context)
    private val api = ApiClient(config)
    private val clipboard = ClipboardController(context)

    suspend fun testConnection(settings: BridgeSettings = config.load()) = withContext(Dispatchers.IO) {
        api.testConnection(settings)
    }

    suspend fun history(settings: BridgeSettings = config.load()) = withContext(Dispatchers.IO) {
        api.history(settings = settings)
    }

    suspend fun sendClipboard(settings: BridgeSettings = config.load()): OperationResult<String> = withContext(Dispatchers.IO) {
        when (val current = clipboard.readCurrent()) {
            is OperationResult.Error -> current
            is OperationResult.Success -> send(current.value, settings)
        }
    }

    suspend fun sendSharedIntent(intent: Intent, settings: BridgeSettings = config.load()): OperationResult<String> =
        withContext(Dispatchers.IO) {
            val uris = sharedUris(intent)
            when {
                uris.isNotEmpty() -> sendSharedUris(uris, intent.type, settings)

                intent.getCharSequenceExtra(Intent.EXTRA_TEXT) != null ->
                    send(OutgoingClipboard.Text(intent.getCharSequenceExtra(Intent.EXTRA_TEXT).toString()), settings)

                else -> OperationResult.Error("The shared item is empty or unsupported.")
            }
        }

    private fun sharedUris(intent: Intent): List<Uri> {
        val result = mutableListOf<Uri>()
        IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java)
            ?.let(result::add)
        IntentCompat.getParcelableArrayListExtra(
            intent,
            Intent.EXTRA_STREAM,
            Uri::class.java,
        )?.let(result::addAll)
        intent.clipData?.let { clip ->
            for (index in 0 until clip.itemCount) {
                clip.getItemAt(index).uri?.let(result::add)
            }
        }
        return result.distinct()
    }

    private fun sendSharedUris(uris: List<Uri>, declaredMime: String?, settings: BridgeSettings): OperationResult<String> {
        val contents = uris.map { uri ->
            val mime = context.contentResolver.getType(uri)
                ?: declaredMime?.takeUnless { it == "*/*" }
                ?: "application/octet-stream"
            OutgoingClipboard.Content(
                uri,
                context.contentResolver.displayName(uri),
                mime,
            )
        }
        return send(
            if (contents.size == 1) contents.first()
            else OutgoingClipboard.ContentGroup(contents),
            settings,
        )
    }

    suspend fun sendUri(uri: Uri, settings: BridgeSettings = config.load()): OperationResult<String> = withContext(Dispatchers.IO) {
        send(
            OutgoingClipboard.Content(
                uri,
                context.contentResolver.displayName(uri),
                context.contentResolver.getType(uri) ?: "application/octet-stream",
            ),
            settings,
        )
    }

    suspend fun sendUris(uris: List<Uri>, settings: BridgeSettings = config.load()): OperationResult<String> = withContext(Dispatchers.IO) {
        sendSharedUris(uris, null, settings)
    }

    private fun send(item: OutgoingClipboard, settings: BridgeSettings): OperationResult<String> {
        val result = when (item) {
            is OutgoingClipboard.Text -> api.uploadText(item.value, settings)
            is OutgoingClipboard.Content -> api.uploadUri(
                context.contentResolver,
                item.uri,
                item.filename,
                item.mime,
                settings,
            )
            is OutgoingClipboard.ContentGroup -> api.uploadUris(
                context.contentResolver,
                item.items,
                settings,
            )
        }
        if (result is OperationResult.Success) {
            val label = when (item) {
                is OutgoingClipboard.Text -> "Text sent to Clipboard Bridge"
                is OutgoingClipboard.Content -> "${item.filename} sent to Clipboard Bridge"
                is OutgoingClipboard.ContentGroup -> "${item.items.size} files sent to Clipboard Bridge"
            }
            notifyIfCurrent(settings) { NotificationHelper.sent(context, label) }
        }
        return result
    }

    suspend fun receiveLatest(notify: Boolean = false, settings: BridgeSettings = config.load()): OperationResult<AppliedItem> =
        receive(null, notify, settings)

    suspend fun receiveItem(id: String, notify: Boolean = false, settings: BridgeSettings = config.load()): OperationResult<AppliedItem> =
        receive(id, notify, settings)

    suspend fun deleteItem(id: String, settings: BridgeSettings = config.load()) = withContext(Dispatchers.IO) {
        api.deleteItem(id, settings)
    }

    private suspend fun receive(id: String?, notify: Boolean, settings: BridgeSettings): OperationResult<AppliedItem> =
        withContext(Dispatchers.IO) {
            val downloaded = if (id == null) {
                api.downloadLatest(context.cacheDir, settings)
            } else {
                api.downloadItem(id, context.cacheDir, settings)
            }
            when (downloaded) {
                is OperationResult.Error -> downloaded
                is OperationResult.Success -> when (val applied = clipboard.apply(downloaded.value, settings)) {
                    is OperationResult.Error -> applied
                    is OperationResult.Success -> {
                        if (notify) notifyIfCurrent(settings) { NotificationHelper.incoming(context, applied.value) }
                        applied
                    }
                }
            }
        }

    fun latestSeenId(settings: BridgeSettings = config.load()) = config.lastSeenId(settings)

    private fun notifyIfCurrent(settings: BridgeSettings, action: () -> Unit) {
        try {
            config.withCurrentConnection(settings, action)
        } catch (_: ConnectionChangedException) {
            // A completed old-source operation must not notify for a newly selected connection.
        } catch (_: Exception) {
            Log.w("ClipboardBridge", "Transfer completed, but its notification could not be displayed.")
        }
    }
}
