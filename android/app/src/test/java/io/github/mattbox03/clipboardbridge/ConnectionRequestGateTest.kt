package io.github.mattbox03.clipboardbridge

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConnectionRequestGateTest {
    private val settings = BridgeSettings()

    @Test fun olderRefreshCannotReplaceTheLatestSuccessOrError() {
        val gate = ConnectionRequestGate()
        val old = gate.begin(settings)
        val latest = gate.begin(settings)
        assertFalse(gate.isCurrent(old, settings))
        assertTrue(gate.isCurrent(latest, settings))
    }

    @Test fun pauseInvalidatesAnInFlightHistoryRequest() {
        val gate = ConnectionRequestGate()
        val old = gate.begin(settings)
        gate.invalidate()
        assertFalse(gate.isCurrent(old, settings))
        assertTrue(gate.isCurrent(gate.begin(settings), settings))
    }

    @Test fun sourceChangeInvalidatesARequestEvenIfNoNewRequestHasStarted() {
        val gate = ConnectionRequestGate()
        val old = gate.begin(settings)
        assertFalse(gate.isCurrent(old, settings.copy(accountMode = true, username = "alice")))
        assertFalse(gate.isCurrent(old, settings.copy(connectionGeneration = 2)))
    }

    @Test fun presentationAndNotificationChangesDoNotInvalidateTheSource() {
        val gate = ConnectionRequestGate()
        val current = gate.begin(settings)
        assertTrue(gate.isCurrent(current, settings.copy(notifyText = false, pollSeconds = 30)))
    }

    @Test fun independentHistoryRefreshDoesNotInvalidateASendOperation() {
        val history = ConnectionRequestGate()
        val operations = ConnectionRequestGate()
        val send = operations.begin(settings)
        history.begin(settings)
        history.invalidate()
        assertTrue(operations.isCurrent(send, settings))
    }

    @Test fun finishingAnOldOperationCannotClearTheNewConnectionsLoadingState() {
        val operations = ConnectionRequestGate()
        val old = operations.begin(settings)
        operations.invalidate()
        val selected = settings.copy(connectionGeneration = 1)
        val current = operations.begin(selected)
        assertFalse(operations.isCurrent(old, selected))
        assertTrue(operations.isCurrent(current, selected))
    }
}
