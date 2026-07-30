package io.github.mattbox03.clipboardbridge

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager

class ClipboardBridgeApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(
                    NotificationHelper.CHANNEL_SYNC,
                    getString(R.string.sync_channel),
                    NotificationManager.IMPORTANCE_LOW,
                ),
                NotificationChannel(
                    NotificationHelper.CHANNEL_INCOMING,
                    getString(R.string.incoming_channel),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ),
                NotificationChannel(
                    NotificationHelper.CHANNEL_OUTGOING,
                    getString(R.string.outgoing_channel),
                    NotificationManager.IMPORTANCE_LOW,
                ),
            ),
        )
    }
}
