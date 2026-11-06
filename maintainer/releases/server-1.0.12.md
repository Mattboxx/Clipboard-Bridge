# Clipboard Bridge Server 1.0.12

## Changes

- Separate Text and File tabs, readable history and mobile-friendly search filters.
- Light, Dark and System themes in a clearly labeled Settings panel; language and
  appearance preferences are retained across the clipboard, login and setup pages.
- Original offline Lucide icons with consistent proportions, stroke and alignment.
- A dedicated `/setup` page with quick Apple, Windows, Android and Docker steps.
  The Apple workflow stays direct Send/Receive using native Shortcuts only.
- Copyable account connection URLs no longer insert passwords. Existing account
  query URLs and the optional request-header authentication remain supported.
  No credential/token is required for the general clipboard unless configured.
- Optional `CLIPBOARD_PUBLIC_ADDRESS` controls the address displayed in setup;
  the QR opens public downloads and never contains pairing secrets or credentials.

## Upgrade

Change the image to `ghcr.io/mattboxx/clipboard-bridge-server:1.0.12`, pull it and
recreate only this container. Keep your environment, published port and existing
`/data` mount. Do not delete volumes. Linux amd64 and arm64 images are provided.

Accounts, stored files/history, browser sessions and existing Apple Shortcut
requests remain compatible. HTTP is not encrypted: use a trusted LAN or private
VPN and do not expose the service directly to the Internet. No AES mode or
Base64 step is required or added.

## Coordinated Delivery

Windows 2.0.21 is released separately. Android beta.12 and signed Apple exports
are unchanged. Docker persistence/upgrade tests, API/GUI checks and browser
layout/icon checks are recorded in the delivery PR; physical device and app-store
installation tests are not claimed. Store adapters update only after the public
multi-architecture image is available.
