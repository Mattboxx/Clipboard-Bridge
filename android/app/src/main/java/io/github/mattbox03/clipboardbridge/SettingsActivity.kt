package io.github.mattbox03.clipboardbridge

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import java.util.Locale

class SettingsActivity : ComponentActivity() {
    private lateinit var config: AppConfig

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        config = AppConfig(this)
        setContent {
            ClipboardBridgeTheme {
                SettingsScreen(
                    initial = config.load(),
                    close = ::finish,
                    save = ::saveSettings,
                    test = { settings, callback ->
                        config.save(settings)
                        lifecycleScope.launch {
                            callback(BridgeRepository(this@SettingsActivity).testConnection())
                        }
                    },
                )
            }
        }
    }

    private fun saveSettings(settings: BridgeSettings) {
        config.save(settings)
        if (settings.autoReceive) {
            ContextCompat.startForegroundService(this, Intent(this, SyncService::class.java))
        } else {
            stopService(Intent(this, SyncService::class.java))
        }
        finish()
    }
}

private data class SettingsCopy(
    val title: String,
    val connection: String,
    val server: String,
    val serverHelp: String,
    val shared: String,
    val account: String,
    val token: String,
    val username: String,
    val password: String,
    val test: String,
    val connected: String,
    val automation: String,
    val receive: String,
    val receiveHelp: String,
    val upload: String,
    val uploadHelp: String,
    val interval: String,
    val notifications: String,
    val notifyText: String,
    val notifyFiles: String,
    val notifySent: String,
    val save: String,
) {
    companion object {
        fun current() = if (Locale.getDefault().language == "it") {
            SettingsCopy(
                "Impostazioni", "Connessione", "Indirizzo server",
                "Esempio: http://192.168.1.20:5088", "Spazio generale", "Account",
                "Token API (opzionale)", "Nome utente", "Password", "Verifica connessione",
                "Connessione riuscita", "Automazione", "Ricezione automatica",
                "Controlla il server anche quando l'app non è aperta.", "Invio automatico visibile",
                "Invia i nuovi appunti quando Clipboard Bridge è in primo piano.",
                "Intervallo di controllo", "Notifiche", "Nuovo testo", "Nuove immagini e file",
                "Conferme di invio", "Salva",
            )
        } else {
            SettingsCopy(
                "Settings", "Connection", "Server address",
                "Example: http://192.168.1.20:5088", "Shared space", "Account",
                "API token (optional)", "Username", "Password", "Test connection",
                "Connection successful", "Automation", "Automatic receiving",
                "Monitor the server even while the app is closed.", "Visible clipboard auto-send",
                "Send new clipboard items while Clipboard Bridge is in the foreground.",
                "Polling interval", "Notifications", "New text", "New images and files",
                "Upload confirmations", "Save",
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScreen(
    initial: BridgeSettings,
    close: () -> Unit,
    save: (BridgeSettings) -> Unit,
    test: (BridgeSettings, (OperationResult<String>) -> Unit) -> Unit,
) {
    val copy = remember { SettingsCopy.current() }
    var settings by remember { mutableStateOf(initial) }
    var showPassword by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<OperationResult<String>?>(null) }
    var testing by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) {}

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(copy.title) },
                navigationIcon = {
                    IconButton(onClick = close) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, null)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF0B1220),
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White,
                ),
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                SettingsSection(copy.connection) {
                    OutlinedTextField(
                        value = settings.serverUrl,
                        onValueChange = {
                            settings = settings.copy(serverUrl = it)
                            testResult = null
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(copy.server) },
                        supportingText = { Text(copy.serverHelp) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    )
                    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                        listOf(copy.shared, copy.account).forEachIndexed { index, label ->
                            SegmentedButton(
                                selected = settings.accountMode == (index == 1),
                                onClick = {
                                    settings = settings.copy(accountMode = index == 1)
                                    testResult = null
                                },
                                shape = SegmentedButtonDefaults.itemShape(index, 2),
                            ) {
                                Text(label)
                            }
                        }
                    }
                    if (settings.accountMode) {
                        OutlinedTextField(
                            value = settings.username,
                            onValueChange = { settings = settings.copy(username = it) },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(copy.username) },
                            singleLine = true,
                        )
                        PasswordField(
                            value = settings.password,
                            onValueChange = { settings = settings.copy(password = it) },
                            label = copy.password,
                            visible = showPassword,
                            toggleVisible = { showPassword = !showPassword },
                        )
                    } else {
                        PasswordField(
                            value = settings.token,
                            onValueChange = { settings = settings.copy(token = it) },
                            label = copy.token,
                            visible = showPassword,
                            toggleVisible = { showPassword = !showPassword },
                        )
                    }
                    OutlinedButton(
                        onClick = {
                            testing = true
                            testResult = null
                            test(settings) {
                                testResult = it
                                testing = false
                            }
                        },
                        enabled = !testing,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (testing) "..." else copy.test)
                    }
                    testResult?.let { result ->
                        val success = result is OperationResult.Success
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(
                                if (success) Icons.Outlined.CheckCircle else Icons.Outlined.ErrorOutline,
                                null,
                                tint = if (success) Color(0xFF16805B) else MaterialTheme.colorScheme.error,
                            )
                            Text(
                                if (success) copy.connected else (result as OperationResult.Error).message,
                                color = if (success) Color(0xFF16805B) else MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                }
            }

            item {
                SettingsSection(copy.automation) {
                    SettingsSwitch(
                        copy.receive,
                        copy.receiveHelp,
                        settings.autoReceive,
                    ) {
                        settings = settings.copy(autoReceive = it)
                        if (
                            it && Build.VERSION.SDK_INT >= 33 &&
                            ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.POST_NOTIFICATIONS,
                            ) != PackageManager.PERMISSION_GRANTED
                        ) {
                            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }
                    }
                    HorizontalDivider()
                    SettingsSwitch(
                        copy.upload,
                        copy.uploadHelp,
                        settings.autoUploadVisible,
                    ) {
                        settings = settings.copy(autoUploadVisible = it)
                    }
                    Text(
                        "${copy.interval}: ${settings.pollSeconds}s",
                        fontWeight = FontWeight.Medium,
                    )
                    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                        val values = listOf(3, 5, 10, 30)
                        values.forEachIndexed { index, seconds ->
                            SegmentedButton(
                                selected = settings.pollSeconds == seconds,
                                onClick = { settings = settings.copy(pollSeconds = seconds) },
                                shape = SegmentedButtonDefaults.itemShape(index, values.size),
                            ) {
                                Text("${seconds}s")
                            }
                        }
                    }
                }
            }

            item {
                SettingsSection(copy.notifications) {
                    SettingsSwitch(copy.notifyText, null, settings.notifyText) {
                        settings = settings.copy(notifyText = it)
                    }
                    SettingsSwitch(copy.notifyFiles, null, settings.notifyFiles) {
                        settings = settings.copy(notifyFiles = it)
                    }
                    SettingsSwitch(copy.notifySent, null, settings.notifySent) {
                        settings = settings.copy(notifySent = it)
                    }
                }
            }

            item {
                Button(
                    onClick = { save(settings) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(copy.save)
                }
            }
        }
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            title.uppercase(Locale.getDefault()),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold,
        )
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(8.dp),
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline,
            ),
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content,
            )
        }
    }
}

@Composable
private fun PasswordField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    visible: Boolean,
    toggleVisible: () -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = true,
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        trailingIcon = {
            IconButton(onClick = toggleVisible) {
                Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility, null)
            }
        },
    )
}

@Composable
private fun SettingsSwitch(
    title: String,
    detail: String?,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Medium)
            if (detail != null) {
                Text(
                    detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
