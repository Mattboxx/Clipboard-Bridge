package io.github.mattbox03.clipboardbridge

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class QuickActionActivity : ComponentActivity() {
    private var actionStarted = false
    private val action: TileAction
        get() = runCatching {
            TileAction.valueOf(intent.getStringExtra(EXTRA_ACTION).orEmpty())
        }.getOrDefault(TileAction.Send)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus || actionStarted) return
        actionStarted = true
        lifecycleScope.launch {
            // Android grants clipboard access only after this activity actually has focus.
            delay(80)
            val result = if (action == TileAction.Receive) {
                BridgeRepository(this@QuickActionActivity).receiveLatest()
            } else {
                BridgeRepository(this@QuickActionActivity).sendClipboard()
            }
            Toast.makeText(
                this@QuickActionActivity,
                when (result) {
                    is OperationResult.Success -> getString(
                        if (action == TileAction.Receive) {
                            R.string.clipboard_received
                        } else {
                            R.string.clipboard_sent
                        },
                    )
                    is OperationResult.Error -> result.message
                },
                Toast.LENGTH_LONG,
            ).show()
            finishAndRemoveTask()
        }
    }

    companion object {
        const val EXTRA_ACTION = "clipboard_action"
    }
}

abstract class BridgeTileService : TileService() {
    protected abstract val action: TileAction

    override fun onStartListening() {
        super.onStartListening()
        restoreTile()
    }

    @SuppressLint("StartActivityAndCollapseDeprecated")
    override fun onClick() {
        super.onClick()
        launchInvisibleAction()
    }

    @SuppressLint("StartActivityAndCollapseDeprecated")
    private fun launchInvisibleAction() {
        // Clipboard reads and writes are reliable only while the helper has focus.
        restoreTile()
        val intent = Intent(this, QuickActionActivity::class.java).apply {
            putExtra(QuickActionActivity.EXTRA_ACTION, this@BridgeTileService.action.name)
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_NEW_DOCUMENT or
                    Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS or
                    Intent.FLAG_ACTIVITY_NO_ANIMATION,
            )
        }
        if (Build.VERSION.SDK_INT >= 34) {
            val pendingIntent = PendingIntent.getActivity(
                this,
                action.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            startActivityAndCollapse(pendingIntent)
        } else {
            @Suppress("DEPRECATION")
            startActivityAndCollapse(intent)
        }
    }

    private fun restoreTile() {
        qsTile.state = Tile.STATE_ACTIVE
        qsTile.label = getString(
            if (action == TileAction.Send) R.string.tile_send else R.string.tile_receive,
        )
        qsTile.updateTile()
    }
}

enum class TileAction { Send, Receive }

class SendClipboardTile : BridgeTileService() {
    override val action = TileAction.Send
}

class ReceiveClipboardTile : BridgeTileService() {
    override val action = TileAction.Receive
}
