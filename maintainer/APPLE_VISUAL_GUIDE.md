# Apple Shortcut illustrations

The public homepage, English setup guides and Italian tutorial embed two real
screenshots from Apple's iOS 26 iPhone User Guide. They illustrate editing
Control Center and opening the controls gallery, not a completed Clipboard
Bridge installation. The following text explains selecting the actual Send and
Receive Shortcuts. No invented iPhone screenshots or looping demo GIFs are used.

## Sources

- [English illustrated Control Center guide](https://support.apple.com/guide/iphone/iph59095ec58/26/ios/26)
- [Italian illustrated Control Center guide](https://support.apple.com/it-it/guide/iphone/iph59095ec58/26/ios/26)
- [Running a Shortcut from Control Center](https://support.apple.com/guide/shortcuts/apd06a9201d4/ios)
- [Share Sheet setup](https://support.apple.com/guide/shortcuts/apd163eb9f95/ios)
- [Home Screen access](https://support.apple.com/guide/shortcuts/apd735880972/ios)

Images stay on `help.apple.com`; they are not copied into this repository or
relicensed under its MIT license. Apple owns the images and interface artwork.
Visible credits identify Apple and make clear that Clipboard Bridge is an
independent project. Do not imply Apple endorsement or present these pictures as
our own physical-device test evidence.

## Behaviour and maintenance

- English pages use Apple's English images; the Italian tutorial uses Italian.
- Images are lazy-loaded, keep explicit dimensions and send no referrer header.
- Both figures link to the corresponding illustrated Apple guide. If an image
  cannot load, `site.js` replaces it with a localized link label rather than a
  broken-image icon. The written setup steps remain available without JavaScript.
- Image URLs are pinned to the documented edition. If Apple removes an asset,
  update the URL from the official guide and inspect the replacement before
  publishing. Do not silently change the instructions to match a guessed UI.
- The tips include Show in Share Sheet, Home Screen access, missing actions and
  a first network transfer. Clipboard Bridge's accepted-input/multi-file recipe
  remains necessary; enabling Share Sheet alone does not rewrite a Shortcut.

After editing, run the public-site tests and check desktop/mobile screenshots.
Also block `help.apple.com` in Playwright once to verify the fallback. Do not
invent private screenshots or use personal devices/accounts as example content.
