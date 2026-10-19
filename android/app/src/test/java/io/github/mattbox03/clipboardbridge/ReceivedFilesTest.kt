package io.github.mattbox03.clipboardbridge

import java.io.File
import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ReceivedFilesTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test fun failedSecondWriteRollsBackTheWholeGroupAndCleansUnusedCacheFiles() {
        val items = sampleFiles()
        val destination = Destination(failAt = "write:two.bin")
        var applied = false
        val failure = runCatching {
            storeReceivedFiles(items, destination) { applied = true }
        }.exceptionOrNull()
        assertSame(destination.failure, failure)
        assertFalse(applied)
        assertEquals(setOf("existing"), destination.targets)
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun clipboardFailureRemovesNewDownloadsButPreservesExistingOnes() {
        val items = sampleFiles()
        val destination = Destination()
        val failure = IOException("Clipboard unavailable")
        assertSame(failure, runCatching {
            storeReceivedFiles(items, destination) { throw failure }
        }.exceptionOrNull())
        assertEquals(setOf("existing"), destination.targets)
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun createFailureStillRemovesEarlierMembersAndAllTemporaryFiles() {
        val items = sampleFiles()
        val destination = Destination(failAt = "create:two.bin")
        assertSame(destination.failure, runCatching {
            storeReceivedFiles(items, destination) { error("Must not apply clipboard") }
        }.exceptionOrNull())
        assertEquals(setOf("existing"), destination.targets)
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun publishFailureRollsBackEveryCreatedTarget() {
        val items = sampleFiles()
        val destination = Destination(failAt = "publish:two.bin")
        assertSame(destination.failure, runCatching {
            storeReceivedFiles(items, destination) { error("Must not apply clipboard") }
        }.exceptionOrNull())
        assertEquals(setOf("existing"), destination.targets)
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun successfulGroupWritesEverythingBeforePublishingAndApplyingClipboard() {
        val items = sampleFiles()
        val original = items.map { it.file.readBytes().toList() }
        val unrelated = File(temporary.root, "unrelated.txt").apply { writeText("must remain") }
        val destination = Destination()
        val result = storeReceivedFiles(items, destination) { saved ->
            destination.events.add("clipboard")
            assertEquals(items.map { it.filename }, saved)
            assertEquals(saved.toSet(), destination.published)
            assertEquals(original, saved.map { destination.written.getValue(it).toList() })
            "applied"
        }
        assertEquals("applied", result)
        assertEquals(listOf("create:one.bin", "write:one.bin", "create:two.bin", "write:two.bin",
            "create:three.bin", "write:three.bin", "publish:one.bin", "publish:two.bin",
            "publish:three.bin", "clipboard"), destination.events)
        assertTrue(items.none { it.file.exists() })
        assertEquals("must remain", unrelated.readText())
        assertEquals(setOf("existing", "one.bin", "two.bin", "three.bin"), destination.targets)
    }

    @Test fun singleFileClipboardFailureAlsoRemovesTheNewDownload() {
        val items = sampleFiles(listOf("single.shortcut"))
        val destination = Destination()
        val failure = IOException("Clipboard unavailable")
        assertSame(failure, runCatching {
            storeReceivedFiles(items, destination) { throw failure }
        }.exceptionOrNull())
        assertEquals(setOf("existing"), destination.targets)
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun emptySingleFileIsPublishedAndAppliedNormally() {
        val items = sampleFiles(listOf("empty.bin"))
        items.single().file.writeBytes(byteArrayOf())
        val destination = Destination()
        assertEquals("empty.bin", storeReceivedFiles(items, destination) { saved -> saved.single() })
        assertEquals(0, destination.written.getValue("empty.bin").size)
        assertEquals(setOf("empty.bin"), destination.published)
        assertFalse(items.single().file.exists())
    }

    @Test fun cleanupFailuresDoNotMaskTheOriginalErrorOrStopOtherCleanupAttempts() {
        val items = sampleFiles()
        val destination = Destination(failAt = "publish:three.bin", refuseRemoval = true)
        var warnings = 0
        assertSame(destination.failure, runCatching {
            storeReceivedFiles(items, destination, { warnings++ }) { error("Must not apply clipboard") }
        }.exceptionOrNull())
        assertEquals(listOf("remove:three.bin", "remove:two.bin", "remove:one.bin"),
            destination.events.filter { it.startsWith("remove:") })
        assertEquals(1, warnings)
        assertTrue(items.none { it.file.exists() })
        // A provider that rejects deletion can leave rows; do not claim atomic rollback.
        assertEquals(setOf("existing", "one.bin", "two.bin", "three.bin"), destination.targets)
    }

    @Test fun failingDiagnosticCallbackDoesNotStopRollback() {
        val items = sampleFiles()
        val destination = Destination(failAt = "publish:three.bin", refuseRemoval = true)
        assertSame(destination.failure, runCatching {
            storeReceivedFiles(items, destination, { error("Logger unavailable") }) {
                error("Must not apply clipboard")
            }
        }.exceptionOrNull())
        assertEquals(3, destination.events.count { it.startsWith("remove:") })
        assertTrue(items.none { it.file.exists() })
    }

    @Test fun emptyGroupNeverCreatesATargetOrAppliesClipboard() {
        val destination = Destination()
        assertTrue(runCatching {
            storeReceivedFiles(emptyList(), destination) { error("Must not apply clipboard") }
        }.exceptionOrNull() is IllegalArgumentException)
        assertTrue(destination.events.isEmpty())
        assertEquals(setOf("existing"), destination.targets)
    }

    private fun sampleFiles(
        names: List<String> = listOf("one.bin", "two.bin", "three.bin"),
    ): List<ReceivedClipboard.FileItem> =
        names.map { name ->
            val file = File(temporary.root, name).apply { writeText("public sample: $name") }
            ReceivedClipboard.FileItem("group-one", file, name, "application/octet-stream")
        }

    private class Destination(
        private val failAt: String? = null,
        private val refuseRemoval: Boolean = false,
    ) : ReceivedFileDestination<String> {
        val targets = mutableSetOf("existing")
        val written = mutableMapOf<String, ByteArray>()
        val published = mutableSetOf<String>()
        val events = mutableListOf<String>()
        val failure = IOException("Injected storage failure")

        private fun checkStep(step: String) {
            events.add(step)
            if (step == failAt) throw failure
        }

        override fun create(item: ReceivedClipboard.FileItem): String {
            checkStep("create:${item.filename}")
            targets.add(item.filename)
            return item.filename
        }

        override fun write(item: ReceivedClipboard.FileItem, target: String) {
            checkStep("write:$target")
            assertTrue(item.file.exists())
            written[target] = item.file.readBytes()
        }

        override fun publish(target: String) {
            checkStep("publish:$target")
            assertTrue(written.containsKey(target))
            published.add(target)
        }

        override fun remove(target: String) {
            events.add("remove:$target")
            if (refuseRemoval) throw IOException("Provider refused deletion")
            targets.remove(target)
            written.remove(target)
            published.remove(target)
        }
    }
}
