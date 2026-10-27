# Validation report

Prepared 27 October 2026 for server **1.0.11**. This report does not claim store
acceptance or installation on a physical CasaOS/ARM64 device.

## Completed locally

- Real Big Bear v1 universal JSON Schema validation (vendored unchanged with license).
- All four Compose definitions parsed by Docker Compose, including resolved
  interpolation, exact image, internal port 5088, persistent `/data`, optional-auth
  defaults and the absence of privileged/host/device/socket requirements.
- Duplicate YAML-key detection and metadata main service/architecture checks.
- Public icon, screenshots, project, documentation and issue URLs returned HTTP 200.
- Big Bear's actual pinned `validate-apps.sh --strict`: 1 passed, zero warnings.
- Actual upstream CasaOS converter: 1 converted, zero errors. Its optional image
  conversion-tool warning does not prevent CasaOS conversion; no all-platform
  conversion claim is made. The supplied reference is the generated output.
- Local image built from the 1.0.11 source. Fourteen disposable Docker tests passed:
  Unicode/text/binary/grouped transfers, account isolation, limits, damaged storage,
  persistence and upgrade from published 1.0.10 with existing data and login cookie.
- Numeric user 1000:1000 tested with a newly created, pre-owned test volume, using
  `TZ=Etc/UTC`; text survives restart. This is not LinuxServer ownership initialization.
- Browser layout checks on the actual running image: desktop 1280px, mobile 390px
  and narrow 320px, all seven languages, top buttons visible, no horizontal overflow.
- Focused server/release/site/Docker-guide tests: 178 passed.
- Full local Python suite: 585 passed, 16 environment-dependent skips. Disposable
  Docker tests were enabled and run separately as described above.

Only uniquely named test containers/volumes were created and removed. No production
container, NAS mount, installed client or private clipboard was used.

## Release gate

Do not send the store proposals until the public **1.0.11** image is published.
Verify the exact tag and both Linux architectures:

```bash
docker buildx imagetools inspect ghcr.io/mattboxx/clipboard-bridge-server:1.0.11
python validation/validate.py --check-links
```

The previous public 1.0.10 manifest was checked for Linux amd64/arm64. Unknown
platform entries in its index are attestations, not additional supported CPUs.
The publication result for 1.0.11 must be recorded separately after the workflow.

## Still manual / not claimed

- CasaOS store UI installation, update and removal on each proposed store.
- Physical ARM64 execution, device-to-device phone tests or NAS installation.
- Maintainer acceptance of a companion utility in HomeAutomation.
- LinuxServer catalog eligibility: current public policy declines PRs.
- Native-speaker linguistic certification. Existing seven-language UI tests only
  check translation completeness and rendering, not human proofreading.

Do not tick those PR checkboxes without carrying out the corresponding checks.
