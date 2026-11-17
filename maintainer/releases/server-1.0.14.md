# Clipboard Bridge Server 1.0.14

## Changes

- **Connect your devices** shows the Send and Receive iPhone Shortcuts as two large
  QR codes. Scan them with the iPhone camera and tap **Add Shortcut**; on the iPhone
  itself, tap a code instead. They replace the links to the `.shortcut` files.
- The Apple steps now say that both Shortcuts ask for their server URL while they
  are added, and that Send already appears in the Share Sheet.
- The Shortcuts are named Send Clipboard and Receive Clipboard across the server,
  website, READMEs and guide.

The QR codes contain only the public iCloud links of the signed Shortcuts: no
server address, account, password or token.

## Upgrade

Change the image to `ghcr.io/mattboxx/clipboard-bridge-server:1.0.14`, pull it and
recreate only this container. Keep your environment, published port and existing
`/data` mount. Do not delete volumes. Linux amd64 and arm64 images are provided.

Accounts, stored files/history, browser sessions, tokens and existing Shortcut
requests remain compatible. HTTP is not encrypted: use a trusted LAN or private
VPN and do not expose the service directly to the Internet.

## Coordinated Delivery

Windows stays at 2.0.22 and Android at 1.0.0-beta.12. The release carries the same
Windows and Android files as 2.0.22 and the current signed Apple Shortcuts.
