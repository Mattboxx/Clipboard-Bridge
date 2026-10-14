# Release candidate: device and installation checks

These checks are **not marked passed** by unit tests or by an HTTP simulation.
Record OS version, app version, server version, shared/account mode and actual result.
Use disposable example content, never personal clipboard data in screenshots.

## Windows x64 and ARM64

- [ ] Fresh standard-user install, no administrator rights; create history and receive a PDF.
- [ ] Upgrade an existing installation; compare credentials, hotkeys, appearance and history.
- [ ] Portable and installer launch only one background instance.
- [ ] Record a History hotkey, save, open/close/reopen three times; tray click only opens/focuses.
- [ ] Text from Word/browser with accents, emoji, flags and joined emoji arrives without styling.
- [ ] Image and PDF previews render; rapid selection/close does not freeze the window.
- [ ] One file and three files restore to Explorer clipboard; group remains one history row.
- [ ] Sending one's own item does not generate an incoming notification or a sync loop.
- [ ] Text/file notification preferences work independently; file notification opens Downloads.
- [ ] Test Client mode and Windows Server mode, including a private-network firewall rule.
- [ ] Disconnect the network/VPN: show offline, keep settings/data and recover after reconnection.

Windows binaries are unsigned. Record the actual SmartScreen/Smart App Control behavior;
do not disable protection or treat a checksum as a trusted signature.

## Android 10+ on a real device

- [ ] Install the beta.11 APK over beta.10 with the same signing certificate; settings survive.
- [ ] Shared space with no token; shared space with token; two isolated accounts.
- [ ] Unicode password/token, including an accented character: no invalid-header exception.
- [ ] Receive Windows/Apple plain text with emoji; paste in a separate application.
- [ ] Share text, a photo, an unfamiliar extension, and a multi-file group from other apps.
- [ ] Quick Settings Send/Receive execute and close the transparent helper, not the main screen.
- [ ] Server history matches the web account; delete one item only after confirmation.
- [ ] New-item notifications obey preferences; receipt is not advertised as guaranteed background pasting.
- [ ] Outgoing auto-detection is tested while the app is visible; background restrictions are disclosed.
- [ ] Disconnect/reconnect Wi-Fi/VPN; stale history disappears and connection errors are understandable.

No Android device was connected during this audit (`adb devices` returned no devices).
JUnit/Gradle success does not replace this list.

## Apple: iPhone, iPad and Mac Shortcuts

- [ ] Import both unmodified signed exports on a supported OS version.
- [ ] Change only the server address and optional existing URL credentials.
- [ ] Send/receive plain text, rich text, emoji, a photo and a PDF.
- [ ] Share a `.rtf` document as a file: original bytes and extension are preserved.
- [ ] Run the documented multi-file variant; receive/extract the transport group correctly.
- [ ] Test a URL-encoded password containing spaces, `&` and accented characters.
- [ ] Run the same two actions from Control Center; test the Mac workflow separately.
- [ ] A real file needs an explicit filename; copied rich text has no filename and is sent as text.

No Apple device was available. Do not distribute changed `.shortcut` files without
on-device verification and valid Apple signing. Existing account/token URLs remain supported.

## LAN/VPN and NAS

- [ ] Phone reaches Windows host over the same LAN; PC must remain awake/running.
- [ ] Phone reaches Docker host over the same LAN; Docker port is not bound only to localhost.
- [ ] Private VPN reachability, ACLs and firewall; no public router port forwarding.
- [ ] If using a subnet router, advertise/approve the route and reserve the host's LAN address.
- [ ] Fresh ZimaOS custom-source install and update preserving the existing `/data` bind mount.
- [ ] Test Umbrel, Portainer, Runtipi and Dockge on actual installations before claiming GUI support passed.

The disposable Docker test uses localhost only. It verifies container behavior and
persistence, not routing from a physical phone, NAS GUI installation or VPN connectivity.

## External beginner pilot

Invite 3-5 volunteers with different devices. Give only the README/download page.
Ask them to time the first successful transfer, identify unclear steps and report
installation warnings. Collect OS/app versions and optional feedback, not clipboard
contents, credentials, household IPs or browsing history. A download is not an installation.
