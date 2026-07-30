package io.github.mattbox03.clipboardbridge

import org.junit.Assert.assertEquals
import org.junit.Test

class AppConfigTest {
    @Test
    fun normalizesServerAddress() {
        assertEquals(
            "http://192.168.1.20:5088",
            AppConfig.normalizeServerUrl("192.168.1.20:5088/"),
        )
        assertEquals(
            "https://bridge.example.test",
            AppConfig.normalizeServerUrl(" https://bridge.example.test/// "),
        )
    }

    @Test
    fun sanitizesDownloadedFilename() {
        assertEquals("report_2026.pdf", sanitizeFilename("report:2026.pdf"))
        assertEquals("clipboard-file", sanitizeFilename("   "))
    }
}
