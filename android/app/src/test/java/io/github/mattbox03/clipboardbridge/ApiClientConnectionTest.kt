package io.github.mattbox03.clipboardbridge

import java.io.File
import java.util.concurrent.atomic.AtomicReference
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ApiClientConnectionTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var server: MockWebServer
    private lateinit var settings: AtomicReference<BridgeSettings>
    private lateinit var api: ApiClient
    private val remembered = mutableListOf<String>()

    @Before fun setUp() {
        server = MockWebServer()
        server.start()
        settings = AtomicReference(BridgeSettings(serverUrl = server.url("/").toString(),
            accountMode = true, username = "alice", password = "sample-only"))
        api = ApiClient(settings::get, { id, _ -> remembered.add(id) }, OkHttpClient())
    }

    @After fun tearDown() { server.shutdown() }

    @Test fun accountSwitchDuringGroupDownloadCannotRerouteMembers() {
        val users = mutableListOf<String?>()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                users.add(request.requestUrl!!.queryParameter("user"))
                return when (request.requestUrl!!.encodedPath) {
                    "/clipboard/latest/raw" -> {
                        settings.set(settings.get().copy(username = "bob"))
                        MockResponse().setHeader("X-Clipboard-Type", "bundle")
                            .setHeader("X-Clipboard-Id", "sample-group").setBody("transport")
                    }
                    "/clipboard/item/sample-group" -> MockResponse().setBody(
                        """{"files":[{"index":0,"filename":"sample.bin"}]}""",
                    )
                    else -> MockResponse().setBody("public sample")
                }
            }
        }
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertTrue(users.all { it == "alice" })
        assertTrue(File(temporary.root, "received").listFiles().orEmpty().isEmpty())
    }

    @Test fun lateTextAfterAccountSwitchIsNotAppliedAsANewConnectionResult() {
        respondAfterSwitch(MockResponse().setHeader("X-Clipboard-Type", "text")
            .setHeader("X-Clipboard-Id", "sample-text").setBody("public sample"))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
    }

    @Test fun lateFileAfterAccountSwitchIsDiscardedWithoutDeletingUnrelatedCache() {
        val unrelated = File(temporary.root, "received").apply { mkdirs() }
            .resolve("unrelated.txt").apply { writeText("must remain") }
        respondAfterSwitch(MockResponse().setHeader("X-Clipboard-Type", "file")
            .setHeader("X-Clipboard-Id", "sample-file").setBody("public sample"))
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), unrelated.parentFile!!.listFiles()!!.toList())
        assertEquals("must remain", unrelated.readText())
    }

    @Test fun lateUploadAcknowledgementDoesNotAdvanceTheNewAccountsSeenId() {
        respondAfterSwitch(MockResponse().setBody("""{"id":"old-account-item"}"""))
        assertTrue(api.uploadText("public sample") is OperationResult.Error)
        assertTrue(remembered.isEmpty())
    }

    @Test fun lateHistoryAfterAccountSwitchIsNotReportedAsCurrent() {
        respondAfterSwitch(MockResponse().setBody("""{"items":[{"id":"alice-only","type":"text"}]}"""))
        assertTrue(api.history() is OperationResult.Error)
    }

    @Test fun lateConnectionCheckDoesNotReportTheOldServerAsConnected() {
        respondAfterSwitch(MockResponse().setBody("""{"items":[]}"""))
        assertTrue(api.testConnection() is OperationResult.Error)
    }

    @Test fun staleExplicitSnapshotIsRejectedBeforeAnyUploadRequest() {
        val previous = settings.get()
        settings.set(previous.copy(username = "bob"))
        server.enqueue(MockResponse().setBody("""{"id":"must-not-be-sent"}"""))
        assertTrue(api.uploadText("public sample", previous) is OperationResult.Error)
        assertEquals(0, server.requestCount)
        assertTrue(remembered.isEmpty())
    }

    @Test fun blankAccountUsernameNeverSilentlyUsesTheSharedSpace() {
        settings.set(settings.get().copy(username = "  "))
        server.enqueue(MockResponse().setBody("""{"items":[]}"""))
        assertTrue(api.history() is OperationResult.Error)
        assertEquals(0, server.requestCount)
    }

    @Test fun sharedSpaceWithoutCredentialsStillWorks() {
        settings.set(settings.get().copy(accountMode = false, username = "", password = ""))
        server.enqueue(MockResponse().setBody("""{"items":[]}"""))
        assertTrue(api.history() is OperationResult.Success)
        val request = server.takeRequest()
        assertEquals(null, request.requestUrl!!.queryParameter("user"))
        assertEquals(null, request.getHeader("X-Auth-Token"))
    }

    @Test fun notificationPreferenceChangesDoNotCancelAHealthyUpload() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                settings.set(settings.get().copy(notifyText = false))
                return MockResponse().setBody("""{"id":"saved-one"}""")
            }
        }
        assertEquals(OperationResult.Success("saved-one"), api.uploadText("public sample"))
        assertEquals(listOf("saved-one"), remembered)
    }

    @Test fun changingServerDuringAGroupDoesNotContactTheNewServer() {
        val other = MockWebServer()
        other.start()
        try {
            other.enqueue(MockResponse().setBody("""{"files":[{"filename":"sample.bin"}]}"""))
            other.enqueue(MockResponse().setBody("public sample"))
            server.dispatcher = object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse {
                    settings.set(settings.get().copy(serverUrl = other.url("/").toString()))
                    return MockResponse().setHeader("X-Clipboard-Type", "bundle")
                        .setHeader("X-Clipboard-Id", "sample-group").setBody("transport")
                }
            }
            assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
            assertEquals(0, other.requestCount)
        } finally {
            other.shutdown()
        }
    }

    @Test fun switchingDuringTheLastBundleMemberDiscardsAllOwnedCacheFiles() {
        val unrelated = File(temporary.root, "received").apply { mkdirs() }
            .resolve("unrelated.txt").apply { writeText("must remain") }
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.requestUrl!!.encodedPath) {
                "/clipboard/latest/raw" -> MockResponse().setHeader("X-Clipboard-Type", "bundle")
                    .setHeader("X-Clipboard-Id", "sample-group").setBody("transport")
                "/clipboard/item/sample-group" -> MockResponse().setBody(
                    """{"files":[{"index":0,"filename":"one.bin"},{"index":1,"filename":"two.bin"}]}""",
                )
                "/clipboard/item/sample-group/file/1/raw" -> {
                    settings.set(settings.get().copy(password = "changed-sample"))
                    MockResponse().setBody("second public sample")
                }
                else -> MockResponse().setBody("first public sample")
            }
        }
        assertTrue(api.downloadLatest(temporary.root) is OperationResult.Error)
        assertEquals(listOf(unrelated), unrelated.parentFile!!.listFiles()!!.toList())
    }

    @Test fun changingAwayAndBackCannotAcknowledgeAnOldUploadToTheNewGeneration() {
        val config = AppConfig(MemoryPreferences())
        config.save(settings.get())
        val original = config.load()
        val bound = ApiClient(config)
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                config.save(original.copy(username = "bob"))
                config.save(original)
                return MockResponse().setBody("""{"id":"obsolete-ack"}""")
            }
        }
        assertTrue(bound.uploadText("public sample") is OperationResult.Error)
        assertEquals("", config.lastSeenId())
    }

    @Test fun draftConnectionTestDoesNotSaveSettingsOrChangeTheActiveAccount() {
        val config = AppConfig(MemoryPreferences())
        config.save(settings.get())
        val original = config.load()
        config.setLastSeenId("keep-original")
        server.enqueue(MockResponse().setBody("""{"items":[]}"""))
        val draft = original.copy(username = "draft-user", password = "draft-sample")
        assertTrue(ApiClient(draft).testConnection() is OperationResult.Success)
        assertEquals("draft-user", server.takeRequest().requestUrl!!.queryParameter("user"))
        assertEquals(original, config.load())
        assertEquals("keep-original", config.lastSeenId())
    }

    @Test fun lateDeleteAcknowledgementIsNotReportedForTheNewAccount() {
        respondAfterSwitch(MockResponse().setBody("""{"status":"ok"}"""))
        assertTrue(api.deleteItem("sample-item") is OperationResult.Error)
    }

    @Test fun settingsChangeBetweenAckValidationAndSeenWriteCannotPolluteTheNewAccount() {
        val config = AppConfig(MemoryPreferences())
        config.save(settings.get())
        val bound = ApiClient(config::load, { id, captured ->
            config.save(captured.copy(username = "bob"))
            config.setLastSeenId(id, captured)
        }, OkHttpClient())
        server.enqueue(MockResponse().setBody("""{"id":"old-account-ack"}"""))
        assertTrue(bound.uploadText("public sample") is OperationResult.Error)
        assertEquals("bob", config.load().username)
        assertEquals("", config.lastSeenId())
    }

    private fun respondAfterSwitch(response: MockResponse) {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                settings.set(settings.get().copy(username = "bob"))
                return response
            }
        }
    }
}
