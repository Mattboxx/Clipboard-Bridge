# Clipboard Bridge release audit

Audit date: **14 October 2026**. Scope: source, public release assets, CI, Docker,
documentation and custom app-store adapters. This is not a penetration-test certificate
or a promise that every operating system/device scenario was exercised.

## Public baseline and candidate

| Component | Public baseline | Prepared candidate |
|---|---|---|
| Main repository | `da3e68ed970245d31263cdd262ba1878a0382e63`; PR #41 merged | `fix/plain-unicode-clipboard`; not merged |
| Windows | 2.0.14; x64 and native ARM64 portable/installers | 2.0.15; rich-text fixes and compatibility checks |
| Android | 1.0.0-beta.10 | 1.0.0-beta.11; Unicode credential-header fix |
| Standalone server | 1.0.7 | 1.0.8; plain-Unicode clipboard conversion |
| App-store repository | `3486a8074c20d50cdd6951a90d524a0d407b0850`; server 1.0.7 | Prepare manifests only; no public 1.0.8 image/catalog yet |
| Apple exports | Existing signed Send/Receive files | Unchanged; no new signed exports claimed |
| Public website | Latest deployed main/Windows 2.0.14 | Candidate download references prepared, not deployed |

Windows 2.0.14 was published while completing the preceding hotkey task, before the
new approval gate arrived. No later stable release, store deployment or promotional
post is authorized without another explicit maintainer approval.

## Findings and decisions

`Bug` is reproduced behavior; `risk` is a technical exposure; `limitation` is an
intentional tradeoff. Do not treat every risk as a reason for mandatory authentication.

| Problem/opportunity | Files | Verified status/category | Priority | Minimum change/decision | Regression risk | Tests |
|---|---|---|---|---|---|---|
| Raw RTF arrives as a file or formatting syntax instead of visible Unicode | Server, Windows, `clipboard_text.py` | Demonstrated bug: `application/rtf` was binary; `text/rtf` was not stripped | P0 transfer correctness | Shared parser for copied text only; preserve actual files | Emoji surrogate pairs, code pages, hyperlinks, whitespace | RTF round trips on both servers, JSON/raw/history, UTF variants |
| Windows app may receive only a Rich Text Format clipboard representation | Windows | Missing format fallback, covered with mocked native APIs | P1 | Prefer Unicode plain text, then read RTF safely if Unicode is absent | Empty Unicode clipboard must stay empty; pointer-size mistakes | Typed 64-bit-safe APIs, lock/unlock/close tests |
| Android passes Unicode passwords/tokens to ASCII-only OkHttp headers | Android API/tests | Demonstrated bug: library throws for those header characters | P0 compatibility | Keep credential URLs; omit invalid optional duplicate headers; URL token fallback | Wrong shared/account routing | JUnit Unicode/whitespace/token and query tests |
| Build context did not exclude Android keys and local runtime data | `.dockerignore`, Dockerfile | Verified risk, not proof of a published secret | P1 | Explicit server-only allowlist; include public license | Missing source file in container | Context test and actual image build |
| Native clients put account secrets in URLs | Windows, Android, server | Intentional compatible transport; maintainer requested no migration | Accepted LAN/VPN limitation | Keep existing URLs across all clients; document clear-text HTTP | Breaking old Shortcuts or selecting wrong account | URL/header account-isolation tests; Docker Apple-URL test |
| Credential URLs may be copied into errors/logs | Windows crash logger, Android errors | Real logging exposure from exception text | P1 | Redact query credential values; do not change authentication | Accidentally hide useful non-secret diagnostics | Windows error log and Kotlin redaction tests |
| Ten-year remembered web session; password changes do not immediately revoke it | Server, SECURITY/DOCKER | Verified persistence/revocation risk | P1, accepted default | Configurable days, unchanged 3650-day default; document explicit global revocation | Unexpected logout on update | Config option and preserved-cookie Docker upgrade test |
| Local configuration/history are not encrypted at rest | Windows config, Android preferences, `/data` | Verified local-storage risk, not remote unauthenticated access | P2 | Document OS-account/backup protection; no DPAPI migration in this release | Downgrade/recovery loss if implemented prematurely | Deferred migration/recovery design |
| Windows uses HTTP only | `server_url`, Settings, GUIDE | Verified architectural limitation | P1 documentation | State LAN/VPN expectation; no universal HTTPS claim | Breaking address settings if redesigned | Existing HTTP client/host tests |
| Windows embedded host has one open shared space | Embedded handler, SECURITY | Intentional minimal host, not an isolated-account server | Accepted limitation | Keep it reachable on trusted LAN/VPN; no new auth or cloud requirement | Phones no longer reaching PC if bound to localhost | Embedded API tests; real LAN still manual |
| Windows files are unsigned | Four downloaded release EXEs, CODE_SIGNING | Authenticode `NotSigned`; no active SignPath config/secrets | Verified state; signing deferred | Do not claim certification or bypass Windows protection | Installation may be blocked by policy | Hash/signature checks; actual installer warnings require pilot |
| History hotkey was open-only | Windows, tests | Already resolved in public 2.0.14 | Done | Preserve open/close/reopen; tray still opens/focuses | Pending Tk timers, duplicates | Native registration/message tests and GUI toggle cleanup tests |
| Android README described separate multi-file rows | `android/README.md` | Demonstrated documentation mismatch with multipart group code | P1 | Document one ordered server group | Confusing restore/deletion expectations | Server/embedded group tests; device flow manual |
| Main documentation listed an obsolete workflow name | DOCKER.md | Documentation defect | P2 | Use actual `Build and publish container` name | None | Repository workflow name inspected |
| New-device install/demo not independently verified | MANUAL_TESTS, launch plan | Test gap, not a proven app failure | P1 launch gate | Real-device checklist and 3-5-person beginner pilot | Unproven promotional claims | Volunteers + actual phone/NAS/VPN tests |

## Already working: do not rewrite

- Shared clipboard remains usable without an account/token on a trusted network.
- Separate account histories and deletes are scoped to the selected account.
- Original file bytes, Unicode filenames, unusual extensions and grouped transfer are tested.
- Latest arrival, not file type, determines the current clipboard.
- Search/type filters/pagination, image/PDF preview, notifications and single instance exist.
- Tk UI commands run on the main thread; network/preview operations are backgrounded.
- Per-user writable Windows storage avoids Program Files write failures.
- Docker has a health endpoint, persistent `/data`, one threaded Gunicorn worker and amd64/arm64 publication.
- English/Italian documentation already opens with beginner setup and explains both modes.
- Website already has canonical/description/Open Graph/structured metadata and direct downloads.
- Custom ZimaOS v2 JSON catalog generation and existing adapters were successful in CI.

## Concrete signature check

The **public release downloads**, not just local build files, were fetched again:

| Artifact | Authenticode | SHA-256 |
|---|---|---|
| x64 portable 2.0.14 | NotSigned, no signer | `0b89e5dee4544cac023c07356b4920db7145a728ed2acc04cfcad0b97ff85d73` |
| x64 installer 2.0.14 | NotSigned, no signer | `d22394b026ec85cb5e2508e375e2e65385d8a0810c1f139e12745defd8930d0c` |
| ARM64 portable 2.0.14 | NotSigned, no signer | `6fba0c39100e38a73ad35b4917d3d1b85ba66e4900a4b5d2d9bd5ac26140acef` |
| ARM64 installer 2.0.14 | NotSigned, no signer | `8dfbe4d474b42a318d4902886b053eab50e717307c6823e8de536eb07c5de84b` |

All match GitHub asset digests and the published release notes. Public installers were
not reinstalled into the user's profile during the audit. Their corresponding x64/ARM64
build checks compare installer payloads with the portable binaries; the current installed
x64 app is 2.0.14. Do not describe this as an independently signed installer payload.

SignPath is skipped at the maintainer's explicit request. No subscription, request,
self-signed certificate or signing bypass was added. Certificate validity cannot be
evaluated for artifacts that have no certificate.

## Automated and container verification

- Full clean staged snapshot: **193 Python tests passed** (server, Windows, text parser, release metadata).
- Covers auth/account isolation, Unicode URLs, unusual files, groups/ZIP validation,
  upload limits, failed writes, concurrency, own-upload notification suppression,
  native hotkeys, GUI cleanup, settings rollback and image/PDF preview paths.
- Android: **7 JUnit tests passed**, debug unit tests and signed release build completed.
- Candidate APK signature verified; signer digest matches public beta.10.
- Actual Docker build succeeded; server-only build context was approximately 66 kB.
- Actual disposable Docker test: fresh 1.0.7, restart, replacement by 1.0.8 using the
  same volume, history/account data and remembered browser cookie preserved.
- Docker RTF -> Unicode, original RTF/PDF group bytes, latest-item metadata,
  unauthorized access and wrong-account item isolation passed.
- Both Compose files validate with `.env.example`, without modifying a real `.env`.

The first restart test initially reused a dynamically published host port. Docker
reassigned it; re-reading `docker port` corrected the test harness. No data-loss bug
was demonstrated by that failure.

Frozen x64 candidate verification passed: 84 bundled native libraries, parser license,
startup, local server, Unicode/RTF, history and duplicate-instance handling. The existing
PC configuration was unchanged and its installed 2.0.14 app was restarted afterwards.
Native ARM64 candidate verification is pending its runner. Previous public verification passed in
[run 38604247649](https://github.com/Mattboxx/Clipboard-Bridge/actions/runs/38604247649).

## CI/repository status at baseline

- `main` has a `Protect main` ruleset; changes use reviewed PRs, not force-pushing.
- Latest main validation, multi-platform container build and Pages runs passed.
- Open Dependabot PRs: #14, #15, #16, #17, #18, #24, #26, #27, #28, #29.
  Do not merge the Gunicorn major update or action updates without their compatibility checks.
- App-store validation, generator and Pages deployment passed at server 1.0.7.
- Tracked Android signing example is public boilerplate; actual `.jks`/keystore settings are ignored.
- This review does not prove every historical commit/cache is secret-free or replace
  a dedicated advisory/dependency scanner. No new credentials or private screenshots
  are added to the prepared source changes.

## Residual checks and roadmap

See [MANUAL_TESTS.md](MANUAL_TESTS.md). No Android device was connected and no Apple
device was available. Do not mark on-device Share/Quick Settings/Control Center or
real VPN routing passed based on tests of HTTP endpoints.

**P0:** final builds, transfer regressions and preservation checks; keep original Apple URLs.

**P1:** real device/pilot checklist; agree on a release without trusted Windows signing;
verify native ARM64 candidate; review prepared docs, image and catalog sequencing.

**P2:** record the demo, useful community posts, directory proposals, and weekly aggregate
feedback. No mandatory cloud, TLS/login, telemetry, DPAPI migration or new pairing feature.

Do not publish new release assets or catalogs until approval. Do not advertise a custom
catalog as official store inclusion. Marketing drafts and external-rule caveats are in
[LAUNCH_PLAN.md](LAUNCH_PLAN.md) and [COMMUNITY_DRAFTS.md](COMMUNITY_DRAFTS.md).

## Prepared source changes

Runtime/release preparation commit: `fb2c1fd`.
Draft review: [PR #42](https://github.com/Mattboxx/Clipboard-Bridge/pull/42).
This PR is intentionally not merged and does not authorize publication.

App-store manifests and the source-tree catalog mirror are prepared for 1.0.8.
Local JSON/YAML validation passes. The catalog CI's public-image check must remain
enabled: it will not pass until the approved multi-architecture image exists.
Do not weaken that gate just to make an unpublished image appear installable.
