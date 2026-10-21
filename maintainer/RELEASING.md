# Coordinated Releases

A release request includes every distribution channel, not just the Windows EXE.
Components have independent version numbers: do not invent a Windows update when
only Android or the server changed. Unchanged signed Apple exports remain reusable.

## Before Publication

1. Compare each component with its last public source/build. List changed and unchanged
   components explicitly; record Windows, Android and standalone server versions.
2. Test the server/API and disposable Docker persistence/upgrade contracts. Run Windows
   tests and applicable native x64/ARM64 package checks. Run Android unit tests, lint
   and a signed release build; compare its signer with the previous public APK.
3. Update current download links, README languages, guide, website, changelog and the
   catalog mirror. Preserve historical evidence and demo capture version captions.
4. Merge through protected PRs only after required checks and review threads pass.

## Publication Order

1. Publish changed Windows binaries with verified source provenance and SHA-256.
2. Publish a changed Android APK with the existing release key, a higher versionCode
   and clear beta status. Keep its own release/download URL explicit.
3. Publish a changed standalone image using a `vX.Y.Z` tag. Check both `linux/amd64`
   and `linux/arm64`, the image revision, `/health`, transfers and persisted data.
4. Only after that image exists, merge the AppStore repository update. Update ZimaOS,
   Umbrel, Runtipi, Portainer's referenced stack and generic Compose instructions.
   Keep app IDs, port, persistent mount and user configuration compatible.
5. Verify generated public `store.json`, index, application metadata and Compose.
   A source-repository merge alone is not a deployed store update.
6. Verify deployed website/tutorial download links, all release asset digests and the
   current README versions. Do not call delivery complete while a channel is pending.

## Boundaries

The custom catalog is not official store inclusion. CI is not a physical phone/NAS
installation test. Windows files remain unsigned until a trusted signing process is
actually enabled. LAN/private-VPN and existing optional Apple credential URLs remain
supported; no release should silently introduce a new pairing/authentication flow.

Record publication commits, workflow runs, image digest, APK signer comparison and
any remaining manual checks in the release notes or delivery PR.
