package io.github.mattbox03.clipboardbridge

import android.Manifest
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()
    private lateinit var clipboard: ClipboardManager
    private val clipboardListener = ClipboardManager.OnPrimaryClipChangedListener {
        viewModel.autoSendClipboardIfAllowed()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        setContent {
            ClipboardBridgeTheme {
                MainScreen(
                    viewModel = viewModel,
                    openSettings = {
                        startActivity(Intent(this, SettingsActivity::class.java))
                    },
                    toggleAutoReceive = ::setAutoReceive,
                )
            }
        }
        if (intent?.action == Intent.ACTION_SEND) {
            viewModel.sendSharedIntent(intent)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.action == Intent.ACTION_SEND) viewModel.sendSharedIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        clipboard.addPrimaryClipChangedListener(clipboardListener)
        if (AppConfig(this).load().autoReceive) {
            ContextCompat.startForegroundService(this, Intent(this, SyncService::class.java))
        }
        viewModel.reloadSettings()
    }

    override fun onPause() {
        clipboard.removePrimaryClipChangedListener(clipboardListener)
        viewModel.clearServerHistory()
        super.onPause()
    }

    private fun setAutoReceive(enabled: Boolean) {
        val config = AppConfig(this)
        config.save(config.load().copy(autoReceive = enabled))
        if (enabled) {
            ContextCompat.startForegroundService(this, Intent(this, SyncService::class.java))
        } else {
            stopService(Intent(this, SyncService::class.java))
        }
        viewModel.reloadSettings()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainScreen(
    viewModel: MainViewModel,
    openSettings: () -> Unit,
    toggleAutoReceive: (Boolean) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val copy = remember { UiCopy.current() }
    val snackbar = remember { SnackbarHostState() }
    val filePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        uri?.let(viewModel::sendUri)
    }
    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted || Build.VERSION.SDK_INT < 33) toggleAutoReceive(true)
    }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    LaunchedEffect(state.settings.serverUrl) {
        while (true) {
            delay(5_000)
            viewModel.refreshSilently()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Clipboard Bridge", fontWeight = FontWeight.SemiBold)
                        Text(
                            "Android",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFB8C7E3),
                        )
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Outlined.Refresh, copy.refresh)
                    }
                    IconButton(onClick = openSettings) {
                        Icon(Icons.Outlined.Settings, copy.settings)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF0B1220),
                    titleContentColor = Color.White,
                    actionIconContentColor = Color.White,
                ),
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(bottom = 28.dp),
        ) {
            item {
                ConnectionBand(state.connection, state.settings, copy)
                ActionPanel(
                    loading = state.loading,
                    onSend = viewModel::sendClipboard,
                    onReceive = viewModel::receiveLatest,
                    onFile = { filePicker.launch(arrayOf("*/*")) },
                    copy = copy,
                )
                SyncControls(
                    settings = state.settings,
                    onAutoReceive = { enabled ->
                        if (
                            enabled &&
                            Build.VERSION.SDK_INT >= 33 &&
                            ContextCompat.checkSelfPermission(
                                viewModel.getApplication(),
                                Manifest.permission.POST_NOTIFICATIONS,
                            ) != PackageManager.PERMISSION_GRANTED
                        ) {
                            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else {
                            toggleAutoReceive(enabled)
                        }
                    },
                    openSettings = openSettings,
                    copy = copy,
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 20.dp, end = 8.dp, top = 24.dp, bottom = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.History, null, tint = MaterialTheme.colorScheme.primary)
                    Column(
                        modifier = Modifier
                            .padding(start = 10.dp)
                            .weight(1f),
                    ) {
                        Text(
                            "${copy.recentItems} (${state.serverHistory.size})",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            copy.serverHistorySource,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            state.settings.serverUrl,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Outlined.Refresh, copy.refresh)
                    }
                }
            }

            if (state.serverHistory.isEmpty()) {
                item {
                    Text(
                        copy.noItems,
                        modifier = Modifier.padding(horizontal = 20.dp, vertical = 28.dp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                items(state.serverHistory, key = { it.id }) { item ->
                    HistoryRow(item, copy) { viewModel.receiveItem(item.id) }
                    HorizontalDivider(modifier = Modifier.padding(start = 64.dp))
                }
            }
        }
    }
}

@Composable
private fun ConnectionBand(state: ConnectionState, settings: BridgeSettings, copy: UiCopy) {
    val (label, color) = when (state) {
        ConnectionState.Checking -> copy.checking to Color(0xFFD49A22)
        ConnectionState.Connected -> copy.connected to Color(0xFF16805B)
        ConnectionState.Disconnected -> copy.disconnected to Color(0xFFB42318)
    }
    val accountLabel = settings.username.trim()
        .takeIf { settings.accountMode && it.isNotEmpty() }
        ?.let { "$label - @$it" }
        ?: label
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF111B2D))
            .padding(horizontal = 20.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(10.dp)
                .background(color, CircleShape),
        )
        Column(modifier = Modifier.padding(start = 10.dp)) {
            Text(accountLabel, color = Color.White, fontWeight = FontWeight.Medium)
            Text(
                settings.serverUrl.ifBlank { copy.serverNotConfigured },
                color = Color(0xFFAEBBD0),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun ActionPanel(
    loading: Boolean,
    onSend: () -> Unit,
    onReceive: () -> Unit,
    onFile: () -> Unit,
    copy: UiCopy,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 22.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = onSend,
                enabled = !loading,
                modifier = Modifier
                    .weight(1f)
                    .height(54.dp),
            ) {
                Icon(Icons.AutoMirrored.Outlined.Send, null)
                Text(copy.sendClipboard, modifier = Modifier.padding(start = 8.dp))
            }
            Button(
                onClick = onReceive,
                enabled = !loading,
                modifier = Modifier
                    .weight(1f)
                    .height(54.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.secondary,
                ),
            ) {
                Icon(Icons.Outlined.Download, null)
                Text(copy.receiveLatest, modifier = Modifier.padding(start = 8.dp))
            }
        }
        OutlinedButton(
            onClick = onFile,
            enabled = !loading,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 12.dp)
                .height(48.dp),
        ) {
            if (loading) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Outlined.UploadFile, null)
            }
            Text(copy.sendFile, modifier = Modifier.padding(start = 8.dp))
        }
    }
}

@Composable
private fun SyncControls(
    settings: BridgeSettings,
    onAutoReceive: (Boolean) -> Unit,
    openSettings: () -> Unit,
    copy: UiCopy,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        shape = RoundedCornerShape(8.dp),
        tonalElevation = 1.dp,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(copy.automaticReceive, fontWeight = FontWeight.SemiBold)
                    Text(
                        copy.backgroundNotice,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = settings.autoReceive, onCheckedChange = onAutoReceive)
            }
            HorizontalDivider()
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = openSettings)
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(copy.autoUploadVisible, fontWeight = FontWeight.Medium)
                    Text(
                        copy.autoUploadHelp,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Icon(Icons.Outlined.Settings, null)
            }
        }
    }
}

@Composable
private fun HistoryRow(item: HistoryItem, copy: UiCopy, onClick: () -> Unit) {
    val icon: ImageVector = when (item.type) {
        "text" -> Icons.Outlined.Description
        "image" -> Icons.Outlined.Image
        else -> Icons.Outlined.UploadFile
    }
    val title = item.filename ?: item.preview ?: when (item.type) {
        "text" -> copy.text
        "image" -> copy.image
        else -> copy.file
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            shape = RoundedCornerShape(6.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Icon(
                icon,
                null,
                modifier = Modifier.padding(10.dp),
                tint = MaterialTheme.colorScheme.primary,
            )
        }
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 12.dp),
        ) {
            Text(title, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(
                item.timestamp.orEmpty(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Icon(Icons.Outlined.Download, copy.receiveLatest)
    }
}
