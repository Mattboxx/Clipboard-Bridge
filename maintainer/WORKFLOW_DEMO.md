# Windows and iPhone illustrated walkthrough

The main demonstration now explains the desktop/mobile workflow, rather than leading
with the optional standalone server web interface.

## What it shows

1. Windows can host the shared clipboard without Docker or another computer.
2. Copy and Send on Windows.
3. Manually trigger the Receive Apple Shortcut, then paste on iPhone.
4. Share a photo with the Send Apple Shortcut.
5. Receive it in the Windows client.
6. Text, photos and files use the same latest-item flow.

The Windows image is an existing real screenshot with public sample data.
The Apple side is a diagram of instructions, not a screenshot or a physical-device
recording. No live phone-to-PC transfer, automatic iOS synchronization or hands-on
phone acceptance test is claimed. Keep the chosen host running on a trusted LAN or VPN.
An optional Docker/NAS host can replace Windows; Android can use the same host.

## Assets and source

- Editable code-native source: `maintainer/workflow-animation.html`.
- English/Italian GIF, MP4 and poster: `docs/assets/demo/windows-iphone-workflow-{en,it}.*`.
- 1000x720, 25.2 seconds, 126 frames at 5 fps. GIF plays once, rather than looping forever.
- The website uses the MP4 with controls, no autoplay. README uses the GIF.
- The original web recording is retained under a collapsed technical section.
- Public sample images only; no credentials, personal clipboard or phone UI is captured.
- No new executable release or change to the seven existing release attachments.

To preview the source locally, open the HTML in a browser. `?lang=it` selects Italian.
For deterministic export, `?capture` disables playback; after `assetsReady` resolves,
call `renderAt(milliseconds)` for frames 0..25000 in 200 ms increments. A GIF/video
encoder can package those frames. The source requires no external network dependency.

## Final SHA-256

```text
ef79d572a1749aed60de5bc6f7e9bda0282391b214fba77a15300112b6a48432  windows-iphone-workflow-en.gif
46559bdb75dff0a9b53e552cb26444ea2284beec0417c2bc221b5b32204d7b4b  windows-iphone-workflow-it.gif
09bc4f9146de146a2e9cacb59eb486a50d67b94d20c830484def6a85a3ee910c  windows-iphone-workflow-en.mp4
ac093a45d77fc9d551c233434f05979269c670e48329fcadd07fe172ddd7bfc8  windows-iphone-workflow-it.mp4
```
