package io.github.mattbox03.clipboardbridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ApiClientTest {
    @Test
    fun accountCredentialsAreAppendedToUrlsWithExistingParameters() {
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
        assertEquals("p@ss word&more", url.queryParameter("password"))
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
}
