package io.github.mattbox03.clipboardbridge

import android.content.Context
import android.content.SharedPreferences

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
    internal val connectionGeneration: Long = 0,
)

class AppConfig internal constructor(private val prefs: SharedPreferences) {
    constructor(context: Context) : this(
        context.getSharedPreferences("clipboard_bridge", Context.MODE_PRIVATE),
    )

    fun load(): BridgeSettings = synchronized(connectionLock) {
        BridgeSettings(
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
            connectionGeneration = prefs.getLong("connection_generation", 0L),
        )
    }

    fun save(settings: BridgeSettings) = synchronized(connectionLock) {
        val previous = load()
        val editor = prefs.edit()
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
        if (!previous.hasSameConnectionDetails(settings)) {
            editor.putLong("connection_generation", previous.connectionGeneration + 1)
                .remove("last_seen_id")
        }
        editor.apply()
    }

    fun lastSeenId(settings: BridgeSettings = load()): String = withCurrentConnection(settings) {
        prefs.getString("last_seen_id", "") ?: ""
    }

    fun setLastSeenId(id: String, settings: BridgeSettings = load()) = withCurrentConnection(settings) {
        prefs.edit().putString("last_seen_id", id).apply()
    }

    internal fun <T> withCurrentConnection(settings: BridgeSettings, action: () -> T): T =
        synchronized(connectionLock) {
            settings.requireCurrentConnection(load())
            action()
        }

    fun suppressClipboardUntil(): Long = prefs.getLong("suppress_clipboard_until", 0L)

    fun suppressClipboardFor(milliseconds: Long = 2500L) {
        prefs.edit().putLong(
            "suppress_clipboard_until",
            System.currentTimeMillis() + milliseconds,
        ).apply()
    }

    companion object {
        private val connectionLock = Any()

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

internal fun BridgeSettings.hasSameConnectionDetails(other: BridgeSettings): Boolean {
    if (AppConfig.normalizeServerUrl(serverUrl) != AppConfig.normalizeServerUrl(other.serverUrl) ||
        accountMode != other.accountMode) return false
    return if (accountMode) {
        username.trim() == other.username.trim() && password == other.password
    } else {
        token.trim() == other.token.trim()
    }
}

internal fun BridgeSettings.matchesConnection(other: BridgeSettings): Boolean =
    connectionGeneration == other.connectionGeneration && hasSameConnectionDetails(other)

internal fun BridgeSettings.requireCurrentConnection(current: BridgeSettings) {
    if (!matchesConnection(current)) throw ConnectionChangedException()
}

internal class ConnectionChangedException : IllegalStateException(
    "Connection settings changed. Retry using the selected server and account.",
)
