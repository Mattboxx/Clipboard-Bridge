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
