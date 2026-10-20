package io.github.mattbox03.clipboardbridge

import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ApiClientTransferTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var server: MockWebServer
    private lateinit var api: ApiClient
    private val remembered = mutableListOf<String>()

    @Before fun setUp() {
        server = MockWebServer()
        server.start()
        val settings = BridgeSettings(serverUrl = server.url("/").toString())
        api = ApiClient(
            { settings },
            { id, _ -> remembered.add(id) },
            OkHttpClient.Builder().retryOnConnectionFailure(false)
                .readTimeout(2, TimeUnit.SECONDS).build(),
        )
    }

    @After fun tearDown() {
        server.shutdown()
    }

    @Test fun explicitTextFileKeepsItsOriginalBytesAndFilename() {
        val raw = "document\r\n\u00e8\uD83D\uDE80".toByteArray()
        server.enqueue(MockResponse().setHeader("X-Clipboard-Type", "file")
            .setHeader("X-Clipboard-Id", "file-one")
            .setHeader("X-Clipboard-Filename", "notes.txt")
            .setHeader("Content-Type", "text/plain; charset=utf-8")
            .setBody(okio.Buffer().write(raw)))
        val result = api.downloadLatest(temporary.root)
        assertTrue(result is OperationResult.Success && result.value is ReceivedClipboard.FileItem)
        val file = (result as OperationResult.Success).value as ReceivedClipboard.FileItem
        assertEquals("notes.txt", file.filename)
        assertArrayEquals(raw, file.file.readBytes())
    }

    @Test fun interruptedSingleDownloadDoesNotLeaveAPartialCacheFile() {
        val unrelated = existingCacheFile()
        server.enqueue(MockResponse().setHeader("X-Clipboard-Type", "file")
            .setHeader("X-Clipboard-Id", "file-one")
            .setHeader("X-Clipboard-Filename", "report.pdf")
            .setBody("x".repeat(12000))
            .setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), File(temporary.root, "received").listFiles()!!.toList())
    }

    @Test fun failedBundleMemberRemovesCompletedAndPartialCacheFiles() {
        val unrelated = existingCacheFile()
        enqueueBundle()
        server.enqueue(MockResponse().setBody("first file"))
        server.enqueue(MockResponse().setBody("x".repeat(12000))
            .setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), File(temporary.root, "received").listFiles()!!.toList())
    }

    @Test fun missingUploadAcknowledgementIsNotASuccessfulSend() {
        server.enqueue(MockResponse().setBody("""{"status":"ok"}"""))
        assertTrue(api.uploadText("public sample") is OperationResult.Error)
        assertTrue(remembered.isEmpty())
    }

    @Test fun wrongJsonEndpointIsNotAConnectedHistory() {
        server.enqueue(MockResponse().setBody("""{"status":"ok","version":"1.0.8"}"""))
        assertTrue(api.testConnection() is OperationResult.Error)
        server.enqueue(MockResponse().setBody("""{"status":"ok"}"""))
        assertTrue(api.history() is OperationResult.Error)
    }

    @Test fun confirmedUploadPreservesUnicodeAndRemembersOnlyTheAcknowledgedId() {
        val text = "public sample\r\n\u00e8 \uD83D\uDE80"
        server.enqueue(MockResponse().setBody("""{"id":"saved-one","type":"text"}"""))
        assertEquals(OperationResult.Success("saved-one"), api.uploadText(text))
        assertEquals(listOf("saved-one"), remembered)
        val request = server.takeRequest()
        assertEquals("/clipboard", request.path)
        assertArrayEquals(text.toByteArray(), request.body.readByteArray())
    }

    @Test fun blankNullAndNumericAcknowledgementsAreRejected() {
        listOf("\"\"", "\"   \"", "null", "23").forEach { value ->
            server.enqueue(MockResponse().setBody("""{"id":$value}"""))
            assertTrue(api.uploadText("public sample") is OperationResult.Error)
        }
        assertTrue(remembered.isEmpty())
    }

    @Test fun rejectedUploadDoesNotRememberAnId() {
        server.enqueue(MockResponse().setResponseCode(503)
            .setBody("""{"id":"not-saved","error":"History is temporarily unavailable."}"""))
        assertTrue(api.uploadText("public sample") is OperationResult.Error)
        assertTrue(remembered.isEmpty())
    }

    @Test fun validEmptyHistoryIsConnectedAndIsStillAnEmptyList() {
        repeat(2) { server.enqueue(MockResponse().setBody("""{"items":[]}""")) }
        assertEquals(OperationResult.Success("Connected"), api.testConnection())
        assertEquals(OperationResult.Success(emptyList<HistoryItem>()), api.history())
    }

    @Test fun textClipboardAndLegacyTextResponsePreserveUnicode() {
        val text = "\u00e8 \uD83D\uDC4B\uD83C\uDFFD\r\nsecond line"
        listOf("text", null).forEach { type ->
            val response = MockResponse().setHeader("X-Clipboard-Id", "text-one")
                .setHeader("Content-Type", "text/plain; charset=utf-8").setBody(text)
            if (type != null) response.setHeader("X-Clipboard-Type", type)
            server.enqueue(response)
            assertEquals(OperationResult.Success(ReceivedClipboard.Text("text-one", text)),
                api.downloadLatest(temporary.root))
        }
        assertTrue(!File(temporary.root, "received").exists())
    }

    @Test fun successfulBundlePreservesOrderDuplicateNamesAndEmptyFiles() {
        enqueueBundle("same.shortcut", "same.shortcut")
        val raw = byteArrayOf(0, 1, -1, 13, 10)
        server.enqueue(MockResponse().setBody(okio.Buffer().write(raw)))
        server.enqueue(MockResponse().setBody(""))
        val result = api.downloadLatest(temporary.root)
        assertTrue(result is OperationResult.Success && result.value is ReceivedClipboard.FileGroup)
        val group = (result as OperationResult.Success).value as ReceivedClipboard.FileGroup
        assertEquals("group-one", group.id)
        assertEquals(listOf("same.shortcut", "same.shortcut"), group.items.map { it.filename })
        assertArrayEquals(raw, group.items[0].file.readBytes())
        assertEquals(0L, group.items[1].file.length())
        assertTrue(group.items[0].file != group.items[1].file)
        assertEquals(2, File(temporary.root, "received").listFiles()!!.size)
    }

    @Test fun rejectedBundleMemberRemovesOnlyThisOperationsFiles() {
        val unrelated = existingCacheFile()
        enqueueBundle()
        server.enqueue(MockResponse().setBody("first file"))
        server.enqueue(MockResponse().setResponseCode(404).setBody("unavailable"))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), File(temporary.root, "received").listFiles()!!.toList())
        assertEquals("must remain", unrelated.readText())
    }

    @Test fun invalidCacheDirectoryDoesNotOverwriteExistingData() {
        val existing = File(temporary.root, "received").apply { writeText("must remain") }
        server.enqueue(MockResponse().setHeader("X-Clipboard-Type", "file")
            .setHeader("X-Clipboard-Id", "file-one").setBody("new file"))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals("must remain", existing.readText())
    }

    @Test fun emptyBundleIsAnErrorAndDoesNotTouchTheCache() {
        val unrelated = existingCacheFile()
        server.enqueue(MockResponse().setHeader("X-Clipboard-Type", "bundle")
            .setHeader("X-Clipboard-Id", "group-one").setBody("transport"))
        server.enqueue(MockResponse().setBody("""{"files":[]}"""))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), File(temporary.root, "received").listFiles()!!.toList())
    }

    private fun existingCacheFile(): File = File(temporary.root, "received").apply { mkdirs() }
        .resolve("unrelated.txt").apply { writeText("must remain") }

    private fun enqueueBundle(firstName: String = "one.bin", secondName: String = "two.bin") {
        server.enqueue(MockResponse().setHeader("X-Clipboard-Type", "bundle")
            .setHeader("X-Clipboard-Id", "group-one").setBody("transport"))
        server.enqueue(MockResponse().setBody("""{"id":"group-one","type":"bundle","files":[
            {"index":0,"filename":"$firstName","mime":"application/octet-stream"},
            {"index":1,"filename":"$secondName","mime":"application/octet-stream"}]}"""))
    }
}
