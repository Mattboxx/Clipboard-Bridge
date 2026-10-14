# Live web demonstration: provenance

Published with the maintainer's explicit request to create and publish a demonstration
and tutorial on 14 October 2026. The Reddit and Dev.to texts are prepared, not posted.

## Actual scope

- Disposable instance of the public Docker image `ghcr.io/mattboxx/clipboard-bridge-server:1.0.8`.
- Loopback-only port, no connection to the user's server or personal clipboard.
- Actual server browser UI, recorded by Playwright with automated UI actions.
- Caption banner added for recording; no fake history items, mocked API responses,
  fabricated device UI or generated phone-to-PC transfer footage.
- Sample Unicode message, project's public SVG icon, generated `notes.txt` and `checklist.csv`.
- Independent HTTP client asserts delivered text (browser-form CRLF), image bytes,
  two-file grouping, each member's original bytes and newer text taking precedence.
- The ZIP actually downloaded via the browser is checked with Python zipfile against
  both originals.
- Exported H.264 MP4, 1280x960, 38.92 seconds, 973 frames; silent, no private metadata.
- Visually inspected representative frames and sample screenshots before publication.

## Public asset

`docs/assets/demo/clipboard-bridge-web-demo.mp4`

SHA-256: `8ef46418bb2952ae48bd3e1d98b65428a5ce8b0b4bc77d342a1fcca28ff8bd9f`

The digest is checked against the final file before committing. Playback and responsive
tutorial layout are checked separately at desktop/mobile viewport sizes.

## Limits

No physical Android or Apple device was connected during capture. Do not describe
this as a real phone-to-PC, native Windows UI or system clipboard synchronization
recording. The tutorial explains those workflows from the code and existing guides;
physical-device acceptance remains pending.

The MP4 is hosted with the website, not added among the release's seven end-user assets.
