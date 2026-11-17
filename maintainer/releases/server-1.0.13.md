# Clipboard Bridge Server 1.0.13

## Changes

- iPhone Safari: the header and the Settings button are no longer covered by the
  status bar, and copy notifications stay above the bottom toolbar. The pages
  declare `viewport-fit=cover` and pad themselves with the device safe areas.
- When you are signed in to an account, **Connect your devices** shows the Send,
  Receive and multi-file URLs with `?user=…&password=…` already filled in and
  URL-encoded. Copy them unchanged into the Shortcuts. Anonymous visitors and the
  shared space never see credentials; signed-out visitors get a sign-in link.
  This reverses the 1.0.12 choice to omit passwords from these URLs.
- The Apple setup steps link directly to the signed Send and Receive Shortcuts
  from the `shortcuts-2026.11.17` release.

URLs that contain a password are as sensitive as the password: anyone who sees a
screenshot of them, or reads logs of a proxy in front of the server, can use the
account. Request-header authentication remains available for anyone who prefers it.

## Upgrade

Change the image to `ghcr.io/mattboxx/clipboard-bridge-server:1.0.13`, pull it and
recreate only this container. Keep your environment, published port and existing
`/data` mount. Do not delete volumes. Linux amd64 and arm64 images are provided.

Accounts, stored files/history, browser sessions, tokens and existing Shortcut
requests remain compatible. HTTP is not encrypted: use a trusted LAN or private
VPN and do not expose the service directly to the Internet.

## Coordinated Delivery

Windows stays at 2.0.22 and Android at 1.0.0-beta.12. The signed Apple Shortcuts
are published separately in `shortcuts-2026.11.17`.
