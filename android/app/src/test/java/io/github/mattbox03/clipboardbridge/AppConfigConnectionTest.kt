package io.github.mattbox03.clipboardbridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

class AppConfigConnectionTest {
    @Test fun accountSwitchDoesNotReuseThePreviousAccountsSeenId() {
        val config = AppConfig(MemoryPreferences())
        config.save(BridgeSettings(accountMode = true, username = "alice", password = "sample-only"))
        config.setLastSeenId("alice-only")
        config.save(config.load().copy(username = "bob"))
        assertEquals("", config.lastSeenId())
    }

    @Test fun serverSwitchDoesNotReuseThePreviousServersSeenId() {
        val config = AppConfig(MemoryPreferences())
        config.setLastSeenId("previous-server")
        config.save(config.load().copy(serverUrl = "http://other.example.test:5088"))
        assertEquals("", config.lastSeenId())
    }

    @Test fun passwordTokenAndModeChangesInvalidateThePreviousConnection() {
        val variants: List<(BridgeSettings) -> BridgeSettings> = listOf(
            { it.copy(token = "different-sample-token") },
            { it.copy(accountMode = true, username = "alice", password = "sample-only") },
        )
        variants.forEach { change ->
            val config = AppConfig(MemoryPreferences())
            val previous = config.load()
            config.setLastSeenId("previous")
            config.save(change(previous))
            assertFalse(previous.matchesConnection(config.load()))
            assertEquals("", config.lastSeenId())
        }
        val config = AppConfig(MemoryPreferences())
        config.save(BridgeSettings(accountMode = true, username = "alice", password = "sample-only"))
        val previous = config.load()
        config.setLastSeenId("previous")
        config.save(previous.copy(password = "changed-sample"))
        assertFalse(previous.matchesConnection(config.load()))
        assertEquals("", config.lastSeenId())
    }

    @Test fun notificationAndAutomationSettingsDoNotResetTheConnectionOrSeenId() {
        val config = AppConfig(MemoryPreferences())
        val previous = config.load()
        config.setLastSeenId("same-server")
        config.save(previous.copy(notifyText = false, notifyFiles = false, notifySent = true,
            autoReceive = true, autoUploadVisible = true, pollSeconds = 20))
        assertTrue(previous.matchesConnection(config.load()))
        assertEquals("same-server", config.lastSeenId())
    }

    @Test fun normalizedAddressesAndUnusedCredentialsDoNotResetTheConnection() {
        val config = AppConfig(MemoryPreferences())
        val previous = config.load()
        config.setLastSeenId("same-server")
        config.save(previous.copy(serverUrl = " ${previous.serverUrl}/// ",
            username = "unused", password = "unused"))
        assertTrue(previous.matchesConnection(config.load()))
        assertEquals("same-server", config.lastSeenId())
    }

    @Test fun legacySettingsAndSeenIdSurviveAnUnrelatedSave() {
        val preferences = MemoryPreferences()
        preferences.edit().putString("last_seen_id", "legacy-item").apply()
        val config = AppConfig(preferences)
        config.save(config.load().copy(notifySent = true))
        assertEquals(0L, config.load().connectionGeneration)
        assertEquals("legacy-item", config.lastSeenId())
    }

    @Test fun changingAwayAndBackStillRejectsTheOriginalSnapshot() {
        val preferences = MemoryPreferences()
        val config = AppConfig(preferences)
        val previous = config.load()
        config.save(previous.copy(serverUrl = "http://other.example.test:5088"))
        config.save(previous)
        val reopened = AppConfig(preferences)
        assertTrue(previous.hasSameConnectionDetails(reopened.load()))
        assertFalse(previous.matchesConnection(reopened.load()))
        assertThrows(ConnectionChangedException::class.java) {
            config.setLastSeenId("obsolete", previous)
        }
        assertEquals("", reopened.lastSeenId())
    }

    @Test fun staleConnectionCannotApplyClipboardOrReadTheNewAccountsSeenId() {
        val preferences = MemoryPreferences()
        val config = AppConfig(preferences)
        val previous = config.load()
        AppConfig(preferences).save(previous.copy(accountMode = true, username = "alice"))
        var applied = false
        assertThrows(ConnectionChangedException::class.java) {
            config.withCurrentConnection(previous) { applied = true }
        }
        assertThrows(ConnectionChangedException::class.java) { config.lastSeenId(previous) }
        assertFalse(applied)
        val message = ConnectionChangedException().message.orEmpty()
        assertFalse(message.contains("alice"))
        assertFalse(message.contains(previous.serverUrl))
    }

    @Test(timeout = 5000) fun settingsSaveCannotInterleaveWithClipboardAndSeenIdCommit() {
        val preferences = MemoryPreferences()
        val config = AppConfig(preferences)
        val previous = config.load()
        val executor = Executors.newSingleThreadExecutor()
        val saverStarted = CountDownLatch(1)
        try {
            val future = config.withCurrentConnection(previous) {
                val save = executor.submit {
                    saverStarted.countDown()
                    AppConfig(preferences).save(previous.copy(serverUrl = "http://other.example.test:5088"))
                }
                assertTrue(saverStarted.await(1, TimeUnit.SECONDS))
                assertThrows(TimeoutException::class.java) { save.get(100, TimeUnit.MILLISECONDS) }
                config.setLastSeenId("applied-to-original", previous)
                assertEquals("applied-to-original", config.lastSeenId(previous))
                save
            }
            future.get(2, TimeUnit.SECONDS)
            assertEquals("", config.lastSeenId())
            assertFalse(previous.matchesConnection(config.load()))
        } finally {
            executor.shutdownNow()
            assertTrue(executor.awaitTermination(2, TimeUnit.SECONDS))
        }
    }
}
