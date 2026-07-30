package io.github.mattbox03.clipboardbridge

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class ShareReceiverActivity : ComponentActivity() {
    private var sending = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        send(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        send(intent)
    }

    private fun send(sharedIntent: Intent) {
        if (sending) return
        sending = true
        lifecycleScope.launch {
            val result = BridgeRepository(this@ShareReceiverActivity)
                .sendSharedIntent(sharedIntent)
            Toast.makeText(
                this@ShareReceiverActivity,
                when (result) {
                    is OperationResult.Success -> getString(R.string.share_sent)
                    is OperationResult.Error -> result.message
                },
                Toast.LENGTH_LONG,
            ).show()
            finishAndRemoveTask()
        }
    }
}
