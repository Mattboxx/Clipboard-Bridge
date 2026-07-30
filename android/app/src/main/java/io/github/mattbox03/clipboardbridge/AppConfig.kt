package io.github.mattbox03.clipboardbridge

import android.content.Context

data class BridgeSettings(
    val serverUrl: String = "http://192.168.1.100:5088",
    val accountMode: Boolean = false,
    val token: String = "",
    val username: String = "",
    val password: String = "",
    val autoReceive: Boolean = false,
    val autoUploadVisible: Boolean = false,
    val pollSeconds: Int = 5,
    val notifyText: Boolean = true,
    val notifyFiles: Boolean = true,
    val notifySent: Boolean = false,
)

class AppConfig(context: Context) {
    private val prefs = context.getSharedPreferences("clipboard_bridge", Context.MODE_PRIVATE)

    fun load() = BridgeSettings(
        serverUrl = prefs.getString("server_url", null) ?: BridgeSettings().serverUrl,
        accountMode = prefs.getBoolean("account_mode", false),
        token = prefs.getString("token", "") ?: "",
        username = prefs.getString("username", "") ?: "",
        password = prefs.getString("password", "") ?: "",
        autoReceive = prefs.getBoolean("auto_receive", false),
        autoUploadVisible = prefs.getBoolean("auto_upload_visible", false),
        pollSeconds = prefs.getInt("poll_seconds", 5).coerceIn(3, 60),
        notifyText = prefs.getBoolean("notify_text", true),
        notifyFiles = prefs.getBoolean("notify_files", true),
        notifySent = prefs.getBoolean("notify_sent", false),
    )

    fun save(settings: BridgeSettings) {
        prefs.edit()
            .putString("server_url", normalizeServerUrl(settings.serverUrl))
            .putBoolean("account_mode", settings.accountMode)
            .putString("token", settings.token.trim())
            .putString("username", settings.username.trim())
            .putString("password", settings.password)
            .putBoolean("auto_receive", settings.autoReceive)
            .putBoolean("auto_upload_visible", settings.autoUploadVisible)
            .putInt("poll_seconds", settings.pollSeconds.coerceIn(3, 60))
            .putBoolean("notify_text", settings.notifyText)
            .putBoolean("notify_files", settings.notifyFiles)
            .putBoolean("notify_sent", settings.notifySent)
            .apply()
    }

    fun lastSeenId(): String = prefs.getString("last_seen_id", "") ?: ""

    fun setLastSeenId(id: String) {
        prefs.edit().putString("last_seen_id", id).apply()
    }

    fun suppressClipboardUntil(): Long = prefs.getLong("suppress_clipboard_until", 0L)

    fun suppressClipboardFor(milliseconds: Long = 2500L) {
        prefs.edit().putLong(
            "suppress_clipboard_until",
            System.currentTimeMillis() + milliseconds,
        ).apply()
    }

    companion object {
        fun normalizeServerUrl(value: String): String {
            var result = value.trim().trimEnd('/')
            if (result.isEmpty()) return ""
            if (!result.startsWith("http://") && !result.startsWith("https://")) {
                result = "http://$result"
            }
            return result
        }
    }
}
