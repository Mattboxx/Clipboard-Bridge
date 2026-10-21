# Release Delivery

When the maintainer requests a release, treat it as coordinated delivery across
the main repository, Windows packages, Android APK, Docker image, custom app-store
repository, website and both README languages. Do not silently stop at one channel.

- Inspect changes since each component's last published build. Increment and build
  changed components; retain the versions of genuinely unchanged components.
- Publish only after applicable tests, package/signature checks and protected-branch
  checks pass. Preserve installed settings and existing persistent data.
- Publish a versioned multi-architecture Docker image before changing catalog image
  references. Update all supported store adapters and the source-tree catalog mirror.
- Verify the public ZimaOS JSON catalog and its generated Compose, not just a merge.
- Update direct download links, current component versions, changelog and guides.
  Verify public assets and deployed pages before reporting delivery complete.
- Keep signed Apple Shortcuts unchanged unless explicitly updated and verified.
- Never claim physical-device tests, trusted Windows signatures or store installation
  tests that were not performed. Report any incomplete channel explicitly.
- Do not change unrelated user edits or replace the installed desktop app without
  authorization. Keep keys, passwords, profiles and sample-private data out of Git.

See `maintainer/RELEASING.md` for publication order and acceptance evidence.
