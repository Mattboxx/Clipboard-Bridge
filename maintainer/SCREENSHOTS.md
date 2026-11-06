# Public interface screenshots

Windows captures refreshed on 2026-10-21. All visible clipboard contents are synthetic public samples.
No personal profile, clipboard, server address or credentials were used.

## Windows

`docs/assets/windows-history.png` is a fresh capture of the real Windows History
window in English, with dark appearance and the real first-page PDF preview enabled. The app used a
temporary profile and a disposable loopback host; clipboard monitoring and system
hotkeys were not started. The pointer was placed on a separate capture-helper
window before capturing History. Only the History window is included.
`windows-history-wide.png` shows the same 2.0.18 candidate in its compact layout.
The screenshots verify UI rendering, not the frozen EXE or a physical phone transfer.

The native capture was returned as JPEG and converted to PNG without changing
the interface, removing elements or painting over the cursor. This replaces the
earlier screenshot that visibly included a pointer on its title bar.
The older connection/automation captures are retained as historical assets, not
embedded as illustrations of the new settings layout.

## Docker web interface

Refreshed on 2026-11-06 for server 1.0.12. `docs/assets/server-web.png` and
`docs/assets/server-history.png` capture the real Flask interface from the release
source, using a temporary profile and a loopback-only test host. Docker runtime,
upgrade and persistence checks are separate; these captures are not evidence of
installing a public image or a store package on a physical NAS.

Browser captures use headless Edge through Playwright at 1440 x 1050, with no UI
overlays, painted changes or cursor. The overview shows the Text/File tabs and
history; the second image contains only the actual History section.

Sample items were uploaded through the HTTP API: synthetic meeting notes, the
project's own clipboard icon, and sample project-notes.pdf/notes.txt in one group.
No personal clipboard contents, account names, passwords or private LAN IPs
appear. The same PNGs are mirrored in the custom store's application assets.

These captures illustrate the UI, not a physical phone-to-PC transfer.
