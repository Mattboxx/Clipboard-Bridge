# Windows Packaging

This directory contains installer inputs, not end-user downloads.

| File | Purpose |
| --- | --- |
| `Clipboard_Bridge_setup.iss` | Inno Setup installer, per-user installation and configuration migration |
| `windows_version_info.txt` | Generated executable metadata, derived from the root `VERSION` |

From the repository root, on x64 Windows:

```bat
scripts\windows\build_release.bat
```

For a portable development executable only:

```bat
scripts\windows\build_client.bat
```

The scripts work from another working directory too. Build prerequisites and
architecture checks are documented in [CONTRIBUTING.md](../../CONTRIBUTING.md).
Native ARM64 packages use the **Build Windows ARM64** workflow, not an x64 build
renamed as ARM64.

## Automated Verification

**Build Windows x64** runs the same release batch script used locally, validates
the native payload, exercises its isolated HTTP host and single-instance behavior,
then installs on a disposable GitHub runner. It compares installed/source executable
hashes and checks existing configuration, local history and embedded-host data.
It never installs onto the maintainer's computer. Real standard-user upgrades,
clipboard/hotkeys, notifications and SmartScreen still need manual acceptance.

The verified `clipboard-bridge-windows-x64` artifact includes the two executables,
SHA-256 checksums, resolved Python package versions and basic build provenance.
Artifacts expire after 14 days. They are unsigned development candidates, not a
new release or proof of trusted code signing. ARM64 retains its separate native
workflow and `clipboard-bridge-windows-arm64` artifact.

PyInstaller is pinned in root `requirements-build.txt`. Runtime requirements remain
ranges; recording actual resolved versions does not make builds byte-reproducible.
Both scripts prefer the active virtual environment over the legacy Python location,
unless `PYTHON_EXE` explicitly selects another interpreter.

## Release Folder Ownership

`scripts/prepare_release_assets.py` copies the current x64 portable/installer and
the two signed Apple exports into `Output/Clipboard.Bridge.Release.V<VERSION>/`.
An optional `android/app/build/outputs/apk/release/app-release.apk` is included only
with valid matching Gradle `output-metadata.json`; its filename uses that build's
version. Metadata checks do not verify an APK's signing certificate.

The helper never clears the folder or removes extra ARM64/APK files added manually.
All required sources must exist and be nonempty before staging. Failed copies
preserve existing managed files and remove only this operation's temporary files.
Replacement is atomic **per file**, not a transaction across the entire set; a late
replacement failure can leave earlier files updated. Stop on failure and verify
the complete intended set before publication. Preserved extras are not revalidated.

## Paths And Metadata

The installer sets `SourceDir=..\..`, so its inputs resolve from the repository
root: `icon.ico` and `dist/Clipboard Bridge.exe`. Output stays in root `Output/`;
moving the installer source must not move user data or release output.

Regenerate version metadata rather than editing it by hand:

```console
python scripts/release_metadata.py --write --check
```

The root scripts, dependency files, application identity, per-user data directory
and release download names are unchanged. The old root build commands have moved
to `scripts/windows/`; update local automation to use the commands above.

Neither build output nor private configuration belongs in Git. Publish verified
end-user artifacts as GitHub Release attachments. See the
[code signing policy](../../CODE_SIGNING.md) before distributing them.
