package io.github.mattbox03.clipboardbridge

internal interface ReceivedFileDestination<T> {
    fun create(item: ReceivedClipboard.FileItem): T
    fun write(item: ReceivedClipboard.FileItem, target: T)
    fun publish(target: T)
    fun remove(target: T)
}

internal fun <T, R> storeReceivedFiles(
    items: List<ReceivedClipboard.FileItem>,
    destination: ReceivedFileDestination<T>,
    onCleanupFailure: () -> Unit = {},
    applyClipboard: (List<T>) -> R,
): R {
    val saved = mutableListOf<T>()
    var cleanupWarningReported = false
    fun cleanup(action: () -> Unit) {
        runCatching(action).onFailure {
            if (!cleanupWarningReported) {
                cleanupWarningReported = true
                runCatching(onCleanupFailure)
            }
        }
    }

    try {
        require(items.isNotEmpty()) { "The file group is empty." }
        // Keep every new target pending until all writes have completed.
        items.forEach { item ->
            val target = destination.create(item)
            saved.add(target)
            destination.write(item, target)
        }
        saved.forEach(destination::publish)
        return applyClipboard(saved)
    } catch (error: Throwable) {
        saved.asReversed().forEach { target -> cleanup { destination.remove(target) } }
        throw error
    } finally {
        items.forEach { item ->
            cleanup {
                check(!item.file.exists() || item.file.delete()) { "Temporary download cleanup failed." }
            }
        }
    }
}
