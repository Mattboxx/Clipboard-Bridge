# Code signing policy

Clipboard Bridge publishes its source code and release files from the
[Mattboxx/Clipboard-Bridge](https://github.com/Mattboxx/Clipboard-Bridge)
repository.

## Verified status

On 14 October 2026, the four Windows artifacts downloaded from release **2.0.14**
(x64/ARM64 portable executables and installers) all returned `NotSigned` from
`Get-AuthenticodeSignature`. Their SHA-256 hashes matched GitHub's asset digests
and the release notes. A checksum verifies integrity, not publisher identity or trust.

SignPath integration is **deferred by the maintainer**. There is no active signing
workflow, certificate or signing secret configured in this repository. Do not
display SignPath credit as though the distributed binaries were certified.

Unsigned builds may trigger SmartScreen or Smart App Control. Do not disable
Windows security or promise that a checksum removes these warnings.

## Current release roles

- Committer and reviewer: [Mattboxx](https://github.com/Mattboxx)
- Release and signing approver: [Mattboxx](https://github.com/Mattboxx)

If trusted signing is enabled in the future, only release artifacts built from
this repository may be submitted for signing.
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
[GitHub Security Advisories](https://github.com/Mattboxx/Clipboard-Bridge/security/advisories/new).
