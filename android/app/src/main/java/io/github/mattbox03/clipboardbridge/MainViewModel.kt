package io.github.mattbox03.clipboardbridge

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MainUiState(
    val connection: ConnectionState = ConnectionState.Checking,
    val serverHistory: List<HistoryItem> = emptyList(),
    val loading: Boolean = false,
    val message: String? = null,
    val settings: BridgeSettings = BridgeSettings(),
)

enum class ConnectionState { Checking, Connected, Disconnected }

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val config = AppConfig(application)
    private val repository = BridgeRepository(application)
    private val _state = MutableStateFlow(MainUiState(settings = config.load()))
    val state = _state.asStateFlow()
    private val historyRequests = ConnectionRequestGate()
    private val operations = ConnectionRequestGate()
    private var historyVisible = true
    private var historyJob: Job? = null

    init {
        refresh()
    }

    fun reloadSettings() {
        val settings = config.load()
        val changed = !_state.value.settings.matchesConnection(settings)
        if (changed) operations.invalidate()
        historyVisible = true
        _state.update {
            it.copy(
                settings = settings,
                serverHistory = emptyList(),
                loading = if (changed) false else it.loading,
                message = if (changed) null else it.message,
            )
        }
        refresh()
    }

    fun clearServerHistory() {
        historyVisible = false
        historyJob?.cancel()
        historyRequests.invalidate()
        _state.update { it.copy(serverHistory = emptyList()) }
    }

    fun refresh() {
        if (!historyVisible) return
        historyJob?.cancel()
        historyJob = viewModelScope.launch {
            _state.update { it.copy(connection = ConnectionState.Checking) }
            loadServerHistory(reportError = true)
        }
    }

    fun refreshSilently() {
        if (!historyVisible || historyJob?.isActive == true) return
        historyJob = viewModelScope.launch {
            loadServerHistory(reportError = false)
        }
    }

    private suspend fun loadServerHistory(reportError: Boolean) {
        if (!historyVisible) return
        val settings = config.load()
        val ticket = historyRequests.begin(settings)
        val history = try {
            repository.history(settings)
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            OperationResult.Error(UiCopy.current().operationFailed)
        }
        if (!historyVisible || !historyRequests.isCurrent(ticket, config.load())) return
        when (history) {
            is OperationResult.Error -> _state.update {
                it.copy(
                    connection = ConnectionState.Disconnected,
                    serverHistory = emptyList(),
                    message = if (reportError) history.message else it.message,
                )
            }

            is OperationResult.Success -> _state.update {
                it.copy(
                    connection = ConnectionState.Connected,
                    serverHistory = history.value,
                )
            }
        }
    }

    fun sendClipboard() = runOperation { settings ->
        repository.sendClipboard(settings).mapSuccess(UiCopy.current().sent)
    }

    fun sendUri(uri: Uri) = runOperation { settings ->
        repository.sendUri(uri, settings).mapSuccess(UiCopy.current().sent)
    }

    fun sendUris(uris: List<Uri>) = runOperation { settings ->
        repository.sendUris(uris, settings).mapSuccess(UiCopy.current().sent)
    }

    fun sendSharedIntent(intent: Intent) = runOperation { settings ->
        repository.sendSharedIntent(intent, settings).mapSuccess(UiCopy.current().sent)
    }

    fun receiveLatest() = runOperation { settings ->
        repository.receiveLatest(settings = settings).mapSuccess(UiCopy.current().received)
    }

    fun receiveItem(id: String, source: BridgeSettings = _state.value.settings) = runOperation(source) { settings ->
        repository.receiveItem(id, settings = settings).mapSuccess(UiCopy.current().received)
    }

    fun deleteItem(id: String, source: BridgeSettings = _state.value.settings) = runOperation(source) { settings ->
        repository.deleteItem(id, settings).mapSuccess(UiCopy.current().deleted)
    }

    fun autoSendClipboardIfAllowed() {
        if (!config.load().autoUploadVisible) return
        if (System.currentTimeMillis() < config.suppressClipboardUntil()) return
        sendClipboard()
    }

    fun clearMessage() {
        _state.update { it.copy(message = null) }
    }

    private fun runOperation(
        settings: BridgeSettings = config.load(),
        block: suspend (BridgeSettings) -> OperationResult<String>,
    ) {
        if (_state.value.loading) return
        if (!settings.matchesConnection(config.load())) {
            refresh()
            return
        }
        val ticket = operations.begin(settings)
        _state.update { it.copy(loading = true, message = null) }
        viewModelScope.launch {
            try {
                val result = block(settings)
                if (!operations.isCurrent(ticket, config.load())) return@launch
                when (result) {
                    is OperationResult.Error -> showError(result.message)
                    is OperationResult.Success -> {
                        _state.update { it.copy(message = result.value) }
                        refresh()
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                if (operations.isCurrent(ticket, config.load())) {
                    showError(UiCopy.current().operationFailed)
                }
            } finally {
                if (operations.isCurrent(ticket, config.load())) {
                    _state.update { it.copy(loading = false) }
                }
            }
        }
    }

    private fun showError(message: String) {
        _state.update { it.copy(message = message, loading = false) }
    }
}

private fun <T> OperationResult<T>.mapSuccess(message: String): OperationResult<String> =
    when (this) {
        is OperationResult.Error -> this
        is OperationResult.Success -> OperationResult.Success(message)
    }
