package io.github.mattbox03.clipboardbridge

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
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

    init {
        refresh()
    }

    fun reloadSettings() {
        _state.update {
            it.copy(
                settings = config.load(),
                serverHistory = emptyList(),
            )
        }
        refresh()
    }

    fun clearServerHistory() {
        _state.update { it.copy(serverHistory = emptyList()) }
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(connection = ConnectionState.Checking) }
            loadServerHistory(reportError = true)
        }
    }

    fun refreshSilently() {
        viewModelScope.launch {
            loadServerHistory(reportError = false)
        }
    }

    private suspend fun loadServerHistory(reportError: Boolean) {
        when (val history = repository.history()) {
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

    fun sendClipboard() = runOperation {
        repository.sendClipboard().mapSuccess(UiCopy.current().sent)
    }

    fun sendUri(uri: Uri) = runOperation {
        repository.sendUri(uri).mapSuccess(UiCopy.current().sent)
    }

    fun sendSharedIntent(intent: Intent) = runOperation {
        repository.sendSharedIntent(intent).mapSuccess(UiCopy.current().sent)
    }

    fun receiveLatest() = runOperation {
        repository.receiveLatest().mapSuccess(UiCopy.current().received)
    }

    fun receiveItem(id: String) = runOperation {
        repository.receiveItem(id).mapSuccess(UiCopy.current().received)
    }

    fun deleteItem(id: String) = runOperation {
        repository.deleteItem(id).mapSuccess(UiCopy.current().deleted)
    }

    fun autoSendClipboardIfAllowed() {
        if (!config.load().autoUploadVisible) return
        if (System.currentTimeMillis() < config.suppressClipboardUntil()) return
        sendClipboard()
    }

    fun clearMessage() {
        _state.update { it.copy(message = null) }
    }

    private fun runOperation(block: suspend () -> OperationResult<String>) {
        if (_state.value.loading) return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, message = null) }
            when (val result = block()) {
                is OperationResult.Error -> showError(result.message)
                is OperationResult.Success -> {
                    _state.update { it.copy(message = result.value) }
                    refresh()
                }
            }
            _state.update { it.copy(loading = false) }
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
