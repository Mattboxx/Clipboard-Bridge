# Code signing policy

Clipboard Bridge publishes its source code and release files from the
[Mattboxx/Clipboard-Bridge](https://github.com/Mattboxx/Clipboard-Bridge)
repository.

## Verified status

On 20 October 2026, the four Windows artifacts from public release **2.0.16**
(x64/ARM64 portable executables and installers) all returned `NotSigned` from
`Get-AuthenticodeSignature`. Their SHA-256 hashes matched GitHub's asset digests
queried again for that release. A checksum verifies integrity, not publisher identity or trust.

| Artifact | SHA-256 |
| --- | --- |
| x64 portable | `9a5f012924c9d24965a8b7a3dd49176aa4e5701f04944b2380c76c4f95350b1a` |
| x64 installer | `77bb8c34ddd00df0cdc568122086d695936bb189a6d6a3882eba6f2dc62c2d22` |
| ARM64 portable | `efc0f4a424bb50a86d8bc626d611478d9dd8295b0aa3ec936a52aed12d4a1bfd` |
| ARM64 installer | `5e79ca07476b57163587b45770761c881460b329afde4fb891aad64fdc6c6942` |

No certificate was present. This is not an independent verification of signatures
on files extracted from the installers; the public installers themselves are unsigned.

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
