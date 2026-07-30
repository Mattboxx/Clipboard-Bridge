package io.github.mattbox03.clipboardbridge

import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.ServiceCompat
import android.content.pm.ServiceInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class SyncService : Service() {
    private val scope = CoroutineScope(Dispatchers.IO)
    private var worker: Job? = null

    override fun onCreate() {
        super.onCreate()
        ServiceCompat.startForeground(
            this,
            NotificationHelper.SYNC_NOTIFICATION_ID,
            NotificationHelper.syncNotification(this),
            if (Build.VERSION.SDK_INT >= 34) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            } else {
                0
            },
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (!AppConfig(applicationContext).load().autoReceive) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (worker?.isActive != true) {
            worker = scope.launch { monitorServer() }
        }
        return START_STICKY
    }

    private suspend fun monitorServer() {
        val repository = BridgeRepository(applicationContext)
        while (scope.isActive) {
            try {
                when (val history = repository.history()) {
                    is OperationResult.Success -> {
                        val newest = history.value.firstOrNull()
                        if (
                            newest != null &&
                            repository.latestSeenId().isNotBlank() &&
                            newest.id != repository.latestSeenId()
                        ) {
                            repository.receiveItem(newest.id, notify = true)
                        } else if (newest != null && repository.latestSeenId().isBlank()) {
                            AppConfig(applicationContext).setLastSeenId(newest.id)
                        }
                    }

                    is OperationResult.Error -> Unit
                }
                delay(AppConfig(applicationContext).load().pollSeconds * 1000L)
            } catch (_: CancellationException) {
                break
            } catch (_: Throwable) {
                delay(10_000)
            }
        }
    }

    override fun onDestroy() {
        worker?.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_STOP = "io.github.mattbox03.clipboardbridge.STOP_SYNC"
    }
}
