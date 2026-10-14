package io.github.mattbox03.clipboardbridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import okhttp3.Request
import org.junit.Test

class ApiClientTest {
    @Test
    fun accountCredentialsRemainInCompatibleUrlsWithExistingParameters() {
        val settings = BridgeSettings(
            accountMode = true,
            username = " Alice Example ",
            password = "p@ss word&more",
        )

        val url = buildRequestUrl(
            "http://192.168.1.20:5088",
            "/clipboard/history?limit=200",
            settings,
        )

        assertEquals("200", url.queryParameter("limit"))
        assertEquals("Alice Example", url.queryParameter("user"))
        assertEquals(settings.password, url.queryParameter("password"))
        assertTrue(canUseCredentialHeaders(settings.username.trim(), settings.password))
    }

    @Test
    fun sharedSpaceDoesNotAddAccountParameters() {
        val url = buildRequestUrl(
            "http://192.168.1.20:5088",
            "/clipboard/latest/raw",
            BridgeSettings(accountMode = false, username = "ignored", password = "ignored"),
        )

        assertNull(url.queryParameter("user"))
        assertNull(url.queryParameter("password"))
    }

    @Test
    fun unicodeCredentialsRemainCompatibleWithUrlAuthentication() {
        val settings = BridgeSettings(accountMode = true, username = "alice", password = "caff\u00e8\u96ea")
        val url = buildRequestUrl("http://192.0.2.10:5088", "/clipboard?limit=1", settings)
        assertFalse(canUseCredentialHeaders(settings.username, settings.password))
        assertEquals(settings.password, url.queryParameter("password"))
        assertEquals("1", url.queryParameter("limit"))
        val tokenUrl = buildRequestUrl("http://192.0.2.10:5088", "/clipboard", BridgeSettings(token = "tok\u00e9n"))
        assertEquals("tok\u00e9n", tokenUrl.queryParameter("token"))
        assertThrows(IllegalArgumentException::class.java) {
            Request.Builder().url("http://192.0.2.10").header("X-Clipboard-Password", settings.password)
        }
    }

    @Test
    fun whitespaceOrControlCharactersDoNotBecomeHttpHeaders() {
        assertFalse(canUseCredentialHeaders(" secret"))
        assertFalse(canUseCredentialHeaders("secret\r\nInjected: true"))
        assertTrue(canUseCredentialHeaders("secret with spaces"))
    }

    @Test
    fun errorsDoNotExposeUrlCredentials() {
        assertEquals("GET http://192.0.2.10/clipboard?user=[redacted]&password=[redacted]&q=notes",
            redactCredentialUrls("GET http://192.0.2.10/clipboard?user=alice&password=p%26ss&q=notes"))
    }
}
