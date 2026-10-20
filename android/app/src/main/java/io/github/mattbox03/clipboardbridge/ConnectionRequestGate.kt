package io.github.mattbox03.clipboardbridge

// Owned by the UI thread. Invalidates late responses after refresh, pause or a source change.
internal class ConnectionRequestGate {
    private var generation = 0L

    class Ticket internal constructor(internal val generation: Long, internal val settings: BridgeSettings)

    fun begin(settings: BridgeSettings): Ticket {
        generation++
        return Ticket(generation, settings)
    }

    fun invalidate() { generation++ }

    fun isCurrent(ticket: Ticket, settings: BridgeSettings): Boolean =
        ticket.generation == generation && ticket.settings.matchesConnection(settings)
}
