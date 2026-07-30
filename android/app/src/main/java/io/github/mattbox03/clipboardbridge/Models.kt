package io.github.mattbox03.clipboardbridge

import android.net.Uri
import java.io.File

data class HistoryItem(
    val id: String,
    val type: String,
    val filename: String?,
    val mime: String?,
    val timestamp: String?,
    val preview: String?,
)

sealed interface OutgoingClipboard {
    data class Text(val value: String) : OutgoingClipboard
    data class Content(val uri: Uri, val filename: String, val mime: String) : OutgoingClipboard
}

sealed interface ReceivedClipboard {
    val id: String

    data class Text(
        override val id: String,
        val value: String,
    ) : ReceivedClipboard

    data class FileItem(
        override val id: String,
        val file: File,
        val filename: String,
        val mime: String,
    ) : ReceivedClipboard
}

sealed interface OperationResult<out T> {
    data class Success<T>(val value: T) : OperationResult<T>
    data class Error(val message: String) : OperationResult<Nothing>
}
