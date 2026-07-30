# Code signing policy

Clipboard Bridge publishes its source code and release files from the
[mattbox03/Clipboard-Bridge](https://github.com/mattbox03/Clipboard-Bridge)
repository.

The project intends to use the following service for trusted Windows
Authenticode signatures:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation.

## Current release roles

- Committer and reviewer: [mattbox03](https://github.com/mattbox03)
- Release and signing approver: [mattbox03](https://github.com/mattbox03)

Only release artifacts built from this repository may be submitted for signing.
The portable Windows executable is signed before it is included in the
installer, and the completed installer is signed separately.

Every public release also includes SHA-256 checksums. Until trusted signing is
active, the release notes and download page clearly identify the Windows files
as unsigned.

## Privacy

Clipboard Bridge does not include telemetry, advertising or usage analytics.

The Windows client transfers clipboard text, images and files only when
requested by the user or when an optional synchronization feature is enabled.
Data is sent only to the server address configured by the user. The server
stores clipboard history in its configured local data directory. Clipboard
contents are not sent to the project maintainers.

GitHub hosts the source repository, release downloads and project website.
Users who choose a VPN or another networking service are also subject to that
service's privacy policy.

## Reporting security issues

Security problems can be reported privately through
[GitHub Security Advisories](https://github.com/mattbox03/Clipboard-Bridge/security/advisories/new).
