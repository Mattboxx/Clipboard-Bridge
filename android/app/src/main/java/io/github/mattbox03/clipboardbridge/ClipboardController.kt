package io.github.mattbox03.clipboardbridge

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import java.io.File

class ClipboardController(private val context: Context) {
    private val clipboard =
        context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    private val config = AppConfig(context)

    fun readCurrent(): OperationResult<OutgoingClipboard> = runCatching {
        val clip = clipboard.primaryClip ?: error("The Android clipboard is empty.")
        val contents = buildList {
            for (index in 0 until clip.itemCount) {
                val uri = clip.getItemAt(index).uri ?: continue
                val mime = context.contentResolver.getType(uri)
                    ?: if (clip.description.mimeTypeCount > 0) {
                        clip.description.getMimeType(index.coerceAtMost(clip.description.mimeTypeCount - 1))
                    } else null
                    ?: "application/octet-stream"
                add(
                    OutgoingClipboard.Content(
                        uri,
                        context.contentResolver.displayName(uri),
                        mime,
                    ),
                )
            }
        }
        if (contents.size > 1) return@runCatching OutgoingClipboard.ContentGroup(contents)
        if (contents.size == 1) return@runCatching contents.first()
        val item = clip.getItemAt(0)
        val text = item.coerceToText(context)?.toString()
            ?: error("This clipboard item cannot be read by Android.")
        OutgoingClipboard.Text(text)
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = { OperationResult.Error(it.message ?: "Clipboard unavailable.") },
    )

    fun apply(received: ReceivedClipboard, settings: BridgeSettings = config.load()): OperationResult<AppliedItem> = runCatching {
        config.withCurrentConnection(settings) { }
        when (received) {
            is ReceivedClipboard.Text -> {
                applyClip(ClipData.newPlainText("Clipboard Bridge", received.value),
                    AppliedItem(received.id, "text", null, null, received.value), settings)
            }

            is ReceivedClipboard.FileItem -> {
                storeReceivedFiles(listOf(received), fileDestination, ::logFileCleanupFailure) { saved ->
                    val uri = saved.first()
                    val clip = ClipData.newUri(context.contentResolver, received.filename, uri)
                    applyClip(clip, AppliedItem(received.id, "file", uri, received.mime, received.filename), settings)
                }
            }

            is ReceivedClipboard.FileGroup -> {
                storeReceivedFiles(received.items, fileDestination, ::logFileCleanupFailure) { saved ->
                    val first = received.items.first()
                    val clip = ClipData.newUri(context.contentResolver, first.filename, saved.first())
                    saved.drop(1).forEach { uri ->
                        clip.addItem(context.contentResolver, ClipData.Item(uri))
                    }
                    applyClip(clip, AppliedItem(
                        received.id,
                        "bundle",
                        saved.first(),
                        first.mime,
                        "${saved.size} files",
                    ), settings)
                }
            }
        }
    }.fold(
        onSuccess = { OperationResult.Success(it) },
        onFailure = {
            received.discardCachedFiles()
            OperationResult.Error(it.message ?: "Unable to store the received item.")
        },
    )

    private fun applyClip(clip: ClipData, item: AppliedItem, settings: BridgeSettings): AppliedItem =
        config.withCurrentConnection(settings) {
            config.suppressClipboardFor()
            clipboard.setPrimaryClip(clip)
            if (item.id.isNotBlank()) config.setLastSeenId(item.id, settings)
            item
        }

    private fun logFileCleanupFailure() {
        Log.w("ClipboardBridge", "Received file cleanup could not be completed.")
    }

    private val fileDestination = object : ReceivedFileDestination<Uri> {
        override fun create(item: ReceivedClipboard.FileItem): Uri {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, item.filename)
                put(MediaStore.Downloads.MIME_TYPE, item.mime)
                put(
                    MediaStore.Downloads.RELATIVE_PATH,
                    "${Environment.DIRECTORY_DOWNLOADS}/Clipboard Bridge",
                )
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            return context.contentResolver.insert(
                MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                values,
            ) ?: error("Android could not create the downloaded file.")
        }

        override fun write(item: ReceivedClipboard.FileItem, target: Uri) {
            context.contentResolver.openOutputStream(target)?.use { output ->
                item.file.inputStream().use { input -> input.copyTo(output) }
            } ?: error("Android could not write the downloaded file.")
        }

        override fun publish(target: Uri) {
            val values = ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }
            check(context.contentResolver.update(target, values, null, null) == 1) {
                "Android could not publish the downloaded file."
            }
        }

        override fun remove(target: Uri) {
            context.contentResolver.delete(target, null, null)
        }
    }
}

data class AppliedItem(
    val id: String,
    val type: String,
    val uri: Uri?,
    val mime: String?,
    val description: String,
)

object NotificationHelper {
    const val CHANNEL_SYNC = "sync_status"
    const val CHANNEL_INCOMING = "incoming_items"
    const val CHANNEL_OUTGOING = "outgoing_results"
    const val SYNC_NOTIFICATION_ID = 100

    fun syncNotification(context: Context): Notification {
        val openApp = PendingIntent.getActivity(
            context,
            10,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(context, CHANNEL_SYNC)
            .setSmallIcon(R.drawable.ic_download)
            .setContentTitle(context.getString(R.string.sync_running))
            .setContentText(context.getString(R.string.sync_running_detail))
            .setContentIntent(openApp)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    fun incoming(context: Context, item: AppliedItem) {
        val settings = AppConfig(context).load()
        if (item.type == "text" && !settings.notifyText) return
        if (item.type != "text" && !settings.notifyFiles) return

        val contentIntent = if (item.uri != null) {
            val view = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(item.uri, item.mime ?: "application/octet-stream")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            PendingIntent.getActivity(
                context,
                item.id.hashCode(),
                view,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        } else {
            PendingIntent.getActivity(
                context,
                item.id.hashCode(),
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
        val text = if (item.type == "text") {
            item.description.take(140)
        } else {
            "${item.description} saved in Downloads/Clipboard Bridge"
        }
        val notification = NotificationCompat.Builder(context, CHANNEL_INCOMING)
            .setSmallIcon(if (item.type == "text") R.drawable.ic_download else R.drawable.ic_upload)
            .setContentTitle(
                if (item.type == "text") "New text received" else "New file received",
            )
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(contentIntent)
            .setAutoCancel(true)
            .build()
        context.getSystemService(NotificationManager::class.java)
            .notify(item.id.hashCode(), notification)
    }

    fun sent(context: Context, description: String) {
        if (!AppConfig(context).load().notifySent) return
        val notification = NotificationCompat.Builder(context, CHANNEL_OUTGOING)
            .setSmallIcon(R.drawable.ic_upload)
            .setContentTitle("Synchronized")
            .setContentText(description)
            .setAutoCancel(true)
            .build()
        context.getSystemService(NotificationManager::class.java)
            .notify((System.nanoTime() and 0x7fffffff).toInt(), notification)
    }

    fun temporaryFileUri(context: Context, file: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.files", file)
}
