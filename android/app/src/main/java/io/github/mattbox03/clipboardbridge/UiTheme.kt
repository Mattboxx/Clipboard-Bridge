package io.github.mattbox03.clipboardbridge

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import java.util.Locale

private val LightColors = lightColorScheme(
    primary = Color(0xFF2563EB),
    onPrimary = Color.White,
    secondary = Color(0xFF16805B),
    onSecondary = Color.White,
    background = Color(0xFFF6F7F9),
    surface = Color.White,
    surfaceVariant = Color(0xFFE9EDF3),
    onSurface = Color(0xFF172033),
    outline = Color(0xFFCBD2DD),
    error = Color(0xFFB42318),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF80AAFF),
    secondary = Color(0xFF62D5A7),
    background = Color(0xFF0B1220),
    surface = Color(0xFF121B2B),
    surfaceVariant = Color(0xFF202B3D),
    onSurface = Color(0xFFF3F5F8),
    outline = Color(0xFF64748B),
    error = Color(0xFFFFB4AB),
)

@Composable
fun ClipboardBridgeTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = MaterialTheme.typography,
        content = content,
    )
}

data class UiCopy(
    val connected: String,
    val disconnected: String,
    val checking: String,
    val serverNotConfigured: String,
    val sendClipboard: String,
    val receiveLatest: String,
    val sendFile: String,
    val automaticReceive: String,
    val autoUploadVisible: String,
    val autoUploadHelp: String,
    val recentItems: String,
    val serverHistorySource: String,
    val refresh: String,
    val settings: String,
    val noItems: String,
    val text: String,
    val file: String,
    val image: String,
    val sent: String,
    val received: String,
    val backgroundNotice: String,
) {
    companion object {
        fun current(): UiCopy = if (Locale.getDefault().language == "it") {
            UiCopy(
                connected = "Connesso",
                disconnected = "Disconnesso",
                checking = "Verifica in corso",
                serverNotConfigured = "Configura l'indirizzo del server",
                sendClipboard = "Invia appunti",
                receiveLatest = "Ricevi ultimo",
                sendFile = "Invia file",
                automaticReceive = "Ricezione automatica",
                autoUploadVisible = "Invio automatico mentre l'app è aperta",
                autoUploadHelp = "Android impedisce alle normali app in background di leggere continuamente gli appunti.",
                recentItems = "Cronologia server",
                serverHistorySource = "Dati live dal server, non salvati sul dispositivo",
                refresh = "Aggiorna",
                settings = "Impostazioni",
                noItems = "Nessun elemento sul server",
                text = "Testo",
                file = "File",
                image = "Immagine",
                sent = "Inviato",
                received = "Ricevuto e copiato",
                backgroundNotice = "Il controllo continuo mostra una notifica permanente.",
            )
        } else {
            UiCopy(
                connected = "Connected",
                disconnected = "Disconnected",
                checking = "Checking connection",
                serverNotConfigured = "Configure the server address",
                sendClipboard = "Send clipboard",
                receiveLatest = "Receive latest",
                sendFile = "Send file",
                automaticReceive = "Automatic receiving",
                autoUploadVisible = "Auto-send while the app is open",
                autoUploadHelp = "Android prevents normal background apps from continuously reading the clipboard.",
                recentItems = "Server history",
                serverHistorySource = "Live server data, not stored on this device",
                refresh = "Refresh",
                settings = "Settings",
                noItems = "No items on the server",
                text = "Text",
                file = "File",
                image = "Image",
                sent = "Sent",
                received = "Received and copied",
                backgroundNotice = "Continuous monitoring displays a permanent notification.",
            )
        }
    }
}
