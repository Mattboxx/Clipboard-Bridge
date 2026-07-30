package io.github.mattbox03.clipboardbridge

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.IntentCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class BridgeRepository(private val context: Context) {
    private val config = AppConfig(context)
    private val api = ApiClient(config)
    private val clipboard = ClipboardController(context)

    suspend fun testConnection() = withContext(Dispatchers.IO) {
        api.testConnection()
    }

    suspend fun history() = withContext(Dispatchers.IO) {
        api.history()
    }

    suspend fun sendClipboard(): OperationResult<String> = withContext(Dispatchers.IO) {
        when (val current = clipboard.readCurrent()) {
            is OperationResult.Error -> current
            is OperationResult.Success -> send(current.value)
        }
    }

    suspend fun sendSharedIntent(intent: Intent): OperationResult<String> =
        withContext(Dispatchers.IO) {
            val uri = IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java)
            when {
                uri != null -> send(
                    OutgoingClipboard.Content(
                        uri,
                        context.contentResolver.displayName(uri),
                        intent.type ?: context.contentResolver.getType(uri)
                        ?: "application/octet-stream",
                    ),
                )

                intent.getCharSequenceExtra(Intent.EXTRA_TEXT) != null ->
                    send(OutgoingClipboard.Text(intent.getCharSequenceExtra(Intent.EXTRA_TEXT).toString()))

                else -> OperationResult.Error("The shared item is empty or unsupported.")
            }
        }

    suspend fun sendUri(uri: Uri): OperationResult<String> = withContext(Dispatchers.IO) {
        send(
            OutgoingClipboard.Content(
                uri,
                context.contentResolver.displayName(uri),
                context.contentResolver.getType(uri) ?: "application/octet-stream",
            ),
        )
    }

    private fun send(item: OutgoingClipboard): OperationResult<String> {
        val result = when (item) {
            is OutgoingClipboard.Text -> api.uploadText(item.value)
            is OutgoingClipboard.Content -> api.uploadUri(
                context.contentResolver,
                item.uri,
                item.filename,
                item.mime,
            )
        }
        if (result is OperationResult.Success) {
            val label = when (item) {
                is OutgoingClipboard.Text -> "Text sent to Clipboard Bridge"
                is OutgoingClipboard.Content -> "${item.filename} sent to Clipboard Bridge"
            }
            NotificationHelper.sent(context, label)
        }
        return result
    }

    suspend fun receiveLatest(notify: Boolean = false): OperationResult<AppliedItem> =
        receive(null, notify)

    suspend fun receiveItem(id: String, notify: Boolean = false): OperationResult<AppliedItem> =
        receive(id, notify)

    private suspend fun receive(id: String?, notify: Boolean): OperationResult<AppliedItem> =
        withContext(Dispatchers.IO) {
            val downloaded = if (id == null) {
                api.downloadLatest(context.cacheDir)
            } else {
                api.downloadItem(id, context.cacheDir)
            }
            when (downloaded) {
                is OperationResult.Error -> downloaded
                is OperationResult.Success -> when (val applied = clipboard.apply(downloaded.value)) {
                    is OperationResult.Error -> applied
                    is OperationResult.Success -> {
                        if (notify) NotificationHelper.incoming(context, applied.value)
                        applied
                    }
                }
            }
        }

    fun latestSeenId() = config.lastSeenId()
}
