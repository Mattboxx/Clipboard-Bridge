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

`docs/assets/server-web.png` and `docs/assets/server-history.png` show the actual
published image `ghcr.io/mattboxx/clipboard-bridge-server:1.0.8`, running in a fresh
disposable container bound only to loopback. Browser captures used Chrome through
Playwright at 1120 x 1080, with no interface modifications or injected captions.
The overview includes the header, text editor and upload area; the history capture
is limited to the actual History panel.

Sample items were uploaded through the HTTP API: public example text and an
example.com link, project-notes.txt and checklist.csv as one file group, and the
project's own clipboard icon as a PNG. The API history was checked independently
to confirm three entries, including both original members of the file group.

These captures illustrate the UI, not a physical phone-to-PC transfer.
