# Product Quality Audit And Acceptance Gates

Updated: **20 October 2026**. Status: **in progress**, not a completed certification
or an assertion that every platform/device scenario has been physically tested.
This is the working plan for improving the product, not just its appearance.

## Scope And Constraints

- Keep the trusted-LAN/private-VPN model, optional accounts and existing Apple URLs.
- Keep Windows host mode usable without Docker or extra hardware.
- Improve demonstrated reliability problems before adding features or abstractions.
- Preserve installed settings, existing data and releases. Test with disposable profiles.
- Keep production dependencies light. The shared storage helper uses only the standard library.
- No new release, installer replacement, store publication or promotional submission
  without the maintainer's approval. A tested development PR is not a published product release.
- Trusted Windows signing is deferred by the maintainer, not silently claimed as complete.

## Verified Public Baseline

| Component | Verified baseline |
| --- | --- |
| Main repository | `118c28260afa92510cd55eea2977f5922ecbd1b1`; repository organization and desktop showcase, PR #49 |
| Public downloads | Windows 2.0.15, Android 1.0.0-beta.11; four Windows EXEs, one APK and two signed Apple exports |
| Standalone server | Public release 1.0.8 |
| Custom AppStore repository | `c902e2a58c5993ac7d02bc5bdcf58329290eb7ae`; server 1.0.8 catalogs |
| Windows signatures | All four public 2.0.15 EXEs are unsigned; hashes match GitHub's current asset digests |
| Source-tree baseline checks | 231 Python tests passed, one optional external-server test skipped before this audit |

The earlier [release audit](RELEASE_AUDIT.md) is historical evidence from 14 October,
not a current claim that its candidate releases remain unpublished.

## Findings And Evidence

| ID | Finding and category | Priority | Files | Evidence / fix | Regression risk and required tests |
| --- | --- | --- | --- | --- | --- |
| Q1 | Existing malformed/unreadable history is treated as empty; bug | P1 data integrity | Server, Windows host and local history | Reproduced against baseline `118c282`: uploading after index corruption returned `200` and replaced the damaged index. Candidate now fails closed and preserves bytes/files. | New stores must still start empty; retain legacy JSON and healthy account access. Fault-injection and real HTTP tests. |
| Q2 | A local cache error can interrupt otherwise healthy remote sharing; bug found while hardening Q1 | P1 usability | Windows monitor, manual actions, Settings and History | Candidate warns once, preserves the cache, keeps remote transfers working and shows a localized history error. | Do not suppress remote-store errors, loop notifications, or turn a successful send into a false failure. Send/sync and GUI regression tests. |
| Q3 | Optional live-server test requires obsolete server 1.0.7; test defect | P1 verification | `tests/test_live_server.py` | Removed the stale hard-coded version. Validate version syntax; allow an explicit expected version. Reuse protocol assertions with a disposable current host. | Must not weaken transfer/content/account assertions. Current client-to-container round trip. |
| Q4 | CI builds an image but does not test its running persistence contract; verification gap | P1 | Validation workflow, `tests/test_container.py` | Candidate adds real container transfers, account isolation, limits, cookie persistence, restart/recreation and corruption/restoration tests. | Never touch production resources; unique containers/volumes and localhost test ports. Cleanup verified after the run. |
| Q5 | Signing documentation verifies an older release; documentation gap | P1 clarity | `CODE_SIGNING.md` | Rechecked 2.0.15 bytes against current GitHub digests and Authenticode. No trusted signature present. | No certification claims, self-signing workaround, or Windows security bypass advice. |
| Q6 | Open dependency/action updates need compatibility and advisory review; risk, not a proven vulnerability | P1 maintenance | Dependency manifests and Dependabot PRs | Open PRs #14-18, #24, #26-29 observed. Review separately rather than blindly merging a Gunicorn major update. | Native x64/ARM64 packaging, runtime image and pipeline compatibility gates. |
| Q7 | Several background operations swallow exceptions; diagnostic risk | P1 operability | Windows, Android service | Requires targeted fault tests and bounded, redacted diagnostics. Do not enable logging of clipboard values or URLs. | Avoid notification floods, leaking credentials, or destabilizing the UI. |
| Q8 | Real device sleep, Share Sheet, Control Center and VPN routing remain unverified; acceptance gap | P1 launch evidence | Platform clients and manual test plan | Automated HTTP tests do not establish these OS-level results. | Run the actual device/NAS/VPN scenarios in [MANUAL_TESTS.md](MANUAL_TESTS.md). |
| Q9 | Configured names can alias one physical account directory; demonstrated isolation bug on Windows | P1 confidentiality | Standalone account storage and server tests | Reproduced two case-distinct users reading one history on NTFS. Separate candidate guard uses actual filesystem identity, denies ambiguous accounts, and preserves the shared space, other users, existing paths and URLs. | Do not merge distinct Linux directories or silently reassign mixed data. Real Windows and Linux server tests, redacted error and permissions checks. |

## Storage Candidate Contract

`clipboard_storage.py` is shared by the standalone server, embedded Windows host
and optional local history. It preserves the existing list-of-objects JSON format.
Malformed JSON, invalid UTF-8, the wrong root shape and read failures are not an
empty store. A missing file still means a new store.

An affected host responds with `503` and `code: history_unavailable`, without
credential values, private paths or clipboard contents. The shared health check
does not certify every account. A damaged account does not block healthy spaces.

Writes use a unique temporary file in the destination directory, flush it before
atomic replacement, and clean up temporary files on failure. Upload rollback also
covers index-read failures. This is **not** an automatic backup system, full schema
validation, multi-process coordination, or a guarantee against every power-loss
scenario. See [recovery instructions](../DOCKER.md#history-storage-errors).

## Acceptance Gates

The broad professional-quality goal is not complete until these gates have direct,
appropriately scoped evidence. Track remaining gaps rather than shrinking the goal
to the work already done.

| Gate | Required evidence | Current status |
| --- | --- | --- |
| Data integrity | Failed writes/reads/corrupt indices preserve existing data; recovery and cleanup work | PR #50 candidate verified locally and in CI; not released |
| Transfer compatibility | Text/Unicode/RTF, images, unusual files and groups on both host modes, with unchanged Apple auth URLs | Existing regression suite plus new disposable-container checks; physical clients still require acceptance |
| Offline and failure UX | Actionable errors, recovery after disconnect, no false send/receive success or silent data loss | Targeted local-cache fix; broader diagnostic review pending |
| Windows packaging | x64/ARM64 native payloads, installer settings preservation, single instance and no Program Files writes | Baseline pipelines verified; rerun native build for the storage candidate |
| Android | Build/tests, account consistency, sharing, notifications, sleep/background disclosures | Existing beta; physical matrix and lifecycle/failure audit pending |
| Docker and stores | Fresh deployment, restart/update, consistent manifests/digests and persistence | New disposable runtime tests passed locally; NAS GUI and real VPN tests still pending |
| Dependency and CI hygiene | Reviewed updates/advisories; explicit test and release gates | Critical Python static checks pass locally; dependency review pending |
| User/developer documentation | Clear first-transfer paths, visible real desktop media, accurate limits, recovery and build instructions | Baseline showcase/layout published; candidate storage/recovery docs prepared |
| Privacy and security | No private material in public assets/logs, account isolation, optional auth kept simple | Existing safeguards and new redacted storage errors tested; continued review required |
| Release quality | Candidate artifacts verified, changelog/checksums, approval before publication | Public versions unchanged; no candidate release authorized or published |
| External usability | Beginner pilot and genuine cross-device demonstration | Not proven by a tray-menu GIF; voluntary pilot and real-device recordings remain open |

## Reproducible Verification

Use a clean checkout/snapshot; unrelated local site edits are not part of the candidate.

```console
python -m pytest -q
python scripts/release_metadata.py --check
docker build -t clipboard-bridge-server:test .
```

Then enable `CLIPBOARD_TEST_IMAGE=clipboard-bridge-server:test` and run
`python -m pytest -q tests/test_container.py`. The container suite uses uniquely
named disposable resources and deletes only those. Windows additionally exercises
its actual client protocol code against that host. No phone, desktop clipboard or
personal deployment is used by this test.

Record clean-tree results, CI runs and PR links here after validation. Do not mark
manual gates passed from source inspection, mocked APIs or successful HTTP alone.

### Candidate Evidence, 20 October

- Clean committed PR #50 source with `CLIPBOARD_TEST_IMAGE` enabled: **282 passed, 1 skipped**.
  The skip is the separately configured external-host test, not the disposable Docker suite.
- All five disposable Docker tests passed locally, including the real Windows
  client's protocol round trips. No test containers or volumes remained afterward.
- Real Tk tests cover localized error display and saving Settings with damaged
  local history. Manual send and automatic sync continue against a healthy remote host.
- Critical static checks (`E9`, `F821`, `F822`, `F823`) and release metadata check passed.
- No authorized Android device was connected when checked. No physical Apple or
  NAS/VPN acceptance results are inferred from the above.
- `pip-audit` 2.10.1 ran successfully in an isolated tooling environment after the
  global command proved unusable. The freshly resolved server/client requirements
  contained **20 dependencies, zero known advisories and zero skipped packages**.
  This does not clear older frozen EXE/APK/container dependency graphs or unknown
  vulnerabilities, and it does not replace compatibility review of open updates.
- The first Linux CI run exposed a test-harness race: Gunicorn can reject a large
  upload before draining its body, and urllib reports BrokenPipe before reading
  the valid 413 response. The test now writes and reads concurrently, still requires
  the actual 413 and confirms history is unchanged; it does not accept a connection
  reset as a successful size-limit check.
- PR #50 latest head `f793076`: all checks passed in
  [validation run 39339209727](https://github.com/Mattboxx/Clipboard-Bridge/actions/runs/39339209727)
  and [native ARM64 run 39339209708](https://github.com/Mattboxx/Clipboard-Bridge/actions/runs/39339209708).
  This verifies the candidate, not publication of new binaries or a store image.
- The follow-up Q9 guard has **85 server tests passing locally on Windows**, with
  actual case/trailing-dot alias behavior and explicit denial checks. Full candidate
  verification before the large-account check: **284 passed, 6 opt-in tests skipped**;
  the five disposable-container checks also passed separately against its rebuilt
  image. The additional large-account check verifies 10,000 users without scanning
  unrelated user directories on each request. Linux/Windows CI for the follow-up
  is still pending.
