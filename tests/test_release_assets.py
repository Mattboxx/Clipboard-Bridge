"""Release staging ownership checks; never build/install into a personal profile."""

import json
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="ascii").strip()


def release_fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text(VERSION, encoding="ascii")
    output = root / "Output"
    output.mkdir()
    for name in (f"Clipboard.Bridge.Portable.Windows.x64.V{VERSION}.exe",
                 f"Clipboard.Bridge_windows_client_and_server_setup_x64_V{VERSION}.exe"):
        (output / name).write_bytes(b"new public sample executable")
    shortcuts = root / "Iphone Shortcuts"
    shortcuts.mkdir()
    for name in ("Load Clipboard.shortcut", "Download Clipboard.shortcut"):
        (shortcuts / name).write_bytes(b"public sample shortcut")
    destination = output / f"Clipboard.Bridge.Release.V{VERSION}"
    destination.mkdir()
    extra = destination / "already-added-arm64.exe"
    extra.write_bytes(b"must remain untouched")
    return destination, extra


def add_apk(root, version="1.0.0-beta.12"):
    directory = root / "android/app/build/outputs/apk/release"
    directory.mkdir(parents=True)
    (directory / "app-release.apk").write_bytes(b"public sample release apk")
    metadata = {"applicationId": "io.github.mattbox03.clipboardbridge", "variantName": "release",
                "elements": [{"filters": [], "versionName": version, "outputFile": "app-release.apk"}]}
    (directory / "output-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


@pytest.fixture
def staging():
    source = ROOT / "scripts/prepare_release_assets.py"
    spec = importlib.util.spec_from_file_location("release_asset_staging_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contents(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


def test_stages_only_managed_end_user_assets_and_keeps_extra_files(tmp_path, staging):
    destination, extra = release_fixture(tmp_path)
    metadata = add_apk(tmp_path)
    result = staging.prepare_release(tmp_path, VERSION)
    assert {path.name for path in result} == {
        f"Clipboard.Bridge.Portable.Windows.x64.V{VERSION}.exe",
        f"Clipboard.Bridge_windows_client_and_server_setup_x64_V{VERSION}.exe",
        "iPhone.Load.Clipboard.shortcut", "iPhone.Download.Clipboard.shortcut",
        f"Clipboard.Bridge.Android.universal.V{metadata['elements'][0]['versionName']}.apk",
    }
    assert all(path.suffix in {".exe", ".shortcut", ".apk"} for path in result)
    assert all(path.parent == destination for path in result)
    assert extra.read_bytes() == b"must remain untouched"
    assert (destination / "iPhone.Load.Clipboard.shortcut").read_bytes() == b"public sample shortcut"
    assert (destination / "Clipboard.Bridge.Android.universal.V1.0.0-beta.12.apk").read_bytes() == b"public sample release apk"


@pytest.mark.parametrize("name", ["Load Clipboard.shortcut", "Download Clipboard.shortcut"])
@pytest.mark.parametrize("empty", [False, True])
def test_missing_or_empty_required_assets_do_not_change_existing_outputs(tmp_path, staging, name, empty):
    destination, _ = release_fixture(tmp_path)
    before = contents(destination)
    source = tmp_path / "Iphone Shortcuts" / name
    if empty:
        source.write_bytes(b"")
    else:
        source.unlink()
    with pytest.raises(ValueError, match="Missing or empty"):
        staging.prepare_release(tmp_path, VERSION)
    assert contents(destination) == before


@pytest.mark.parametrize("value", ["9.9.9", "../outside", "2.0.15&exit", ""])
def test_wrong_or_unsafe_versions_are_rejected_before_writing(tmp_path, staging, value):
    destination, _ = release_fixture(tmp_path)
    before = contents(destination)
    with pytest.raises(ValueError, match="VERSION"):
        staging.prepare_release(tmp_path, value)
    assert contents(destination) == before


def test_apk_without_output_metadata_is_not_mislabeled(tmp_path, staging):
    destination, _ = release_fixture(tmp_path)
    add_apk(tmp_path)
    (tmp_path / "android/app/build/outputs/apk/release/output-metadata.json").unlink()
    before = contents(destination)
    with pytest.raises(OSError):
        staging.prepare_release(tmp_path, VERSION)
    assert contents(destination) == before


@pytest.mark.parametrize("raw", ["not json", "null", "[]"])
def test_malformed_android_metadata_does_not_publish_any_assets(tmp_path, staging, raw):
    destination, _ = release_fixture(tmp_path)
    add_apk(tmp_path)
    (tmp_path / "android/app/build/outputs/apk/release/output-metadata.json").write_text(raw)
    before = contents(destination)
    with pytest.raises(ValueError):
        staging.prepare_release(tmp_path, VERSION)
    assert contents(destination) == before


@pytest.mark.parametrize("key,value", [("applicationId", "example.other"), ("variantName", "debug"),
                                       ("elements", []), ("elements", None)])
def test_invalid_android_build_identity_is_rejected(tmp_path, staging, key, value):
    destination, _ = release_fixture(tmp_path)
    metadata = add_apk(tmp_path)
    metadata[key] = value
    (tmp_path / "android/app/build/outputs/apk/release/output-metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        staging.prepare_release(tmp_path, VERSION)
    assert list(destination.iterdir()) == [destination / "already-added-arm64.exe"]


@pytest.mark.parametrize("key,value", [("versionName", "../outside"), ("versionName", 12),
                                       ("outputFile", "../other.apk"), ("filters", [{"filterType": "ABI"}])])
def test_unsafe_or_split_apk_metadata_is_rejected(tmp_path, staging, key, value):
    destination, _ = release_fixture(tmp_path)
    metadata = add_apk(tmp_path)
    metadata["elements"][0][key] = value
    (tmp_path / "android/app/build/outputs/apk/release/output-metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        staging.prepare_release(tmp_path, VERSION)
    assert list(destination.iterdir()) == [destination / "already-added-arm64.exe"]


def test_copy_failure_preserves_old_managed_files_and_removes_only_owned_temporaries(tmp_path, staging, monkeypatch):
    destination, _ = release_fixture(tmp_path)
    for _, name in staging.asset_plan(tmp_path, VERSION):
        (destination / name).write_bytes(b"previous build")
    (destination / ".clipboard-release-existing.tmp").write_bytes(b"not owned by this operation")
    before = contents(destination)
    copy = staging.shutil.copyfileobj
    calls = 0

    def fail_second(source, output):
        nonlocal calls
        calls += 1
        if calls == 2:
            output.write(b"partial")
            raise OSError("Injected copy failure")
        copy(source, output)

    monkeypatch.setattr(staging.shutil, "copyfileobj", fail_second)
    with pytest.raises(OSError, match="Injected copy failure"):
        staging.prepare_release(tmp_path, VERSION)
    assert contents(destination) == before


def test_replace_failure_preserves_previous_files_and_cleans_staging(tmp_path, staging, monkeypatch):
    destination, _ = release_fixture(tmp_path)
    before = contents(destination)

    def fail_replace(*_):
        raise OSError("Injected replace failure")

    monkeypatch.setattr(staging.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Injected replace failure"):
        staging.prepare_release(tmp_path, VERSION)
    assert contents(destination) == before


def test_late_replace_failure_is_an_error_and_never_removes_unrelated_files(tmp_path, staging, monkeypatch):
    destination, extra = release_fixture(tmp_path)
    plan = staging.asset_plan(tmp_path, VERSION)
    for _, name in plan:
        (destination / name).write_bytes(b"previous build")
    replace = staging.os.replace
    calls = 0

    def fail_second(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Injected late replace failure")
        replace(source, target)

    monkeypatch.setattr(staging.os, "replace", fail_second)
    with pytest.raises(OSError, match="late replace failure"):
        staging.prepare_release(tmp_path, VERSION)
    # Replacement is atomic per file, not a transaction across the whole release.
    assert (destination / plan[0][1]).read_bytes() == plan[0][0].read_bytes()
    assert (destination / plan[1][1]).read_bytes() == b"previous build"
    assert extra.read_bytes() == b"must remain untouched"
    assert not list(destination.glob(".clipboard-release-*.tmp"))


def test_destination_directory_conflict_is_rejected_before_any_copy(tmp_path, staging):
    destination, extra = release_fixture(tmp_path)
    (destination / "iPhone.Load.Clipboard.shortcut").mkdir()
    with pytest.raises(ValueError, match="directory occupies"):
        staging.prepare_release(tmp_path, VERSION)
    assert extra.read_bytes() == b"must remain untouched"
    assert len(list(destination.iterdir())) == 2


def test_symlinked_destination_is_not_followed(tmp_path, staging):
    destination, _ = release_fixture(tmp_path)
    (destination / "already-added-arm64.exe").unlink()
    destination.rmdir()
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_bytes(b"must remain untouched")
    try:
        destination.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable to this test user")
    with pytest.raises(ValueError, match="inside the project"):
        staging.prepare_release(tmp_path, VERSION)
    assert list(outside.iterdir()) == [marker]
    assert marker.read_bytes() == b"must remain untouched"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junction behavior")
def test_junction_to_another_project_directory_is_not_followed(tmp_path, staging):
    destination, _ = release_fixture(tmp_path)
    (destination / "already-added-arm64.exe").unlink()
    destination.rmdir()
    target = tmp_path / "other release folder"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_bytes(b"must remain untouched")
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(destination), str(target)],
                            capture_output=True, timeout=10)
    if result.returncode:
        pytest.skip("Directory junctions are unavailable to this test user")
    with pytest.raises(ValueError, match="inside the project"):
        staging.prepare_release(tmp_path, VERSION)
    assert list(target.iterdir()) == [marker]
    assert marker.read_bytes() == b"must remain untouched"


def run_batch_preparation(root):
    """Execute the shipping preparation stage, without running pip, builds or installers."""
    script = (ROOT / "scripts/windows/build_release.bat").read_text(encoding="utf-8")
    stage = script[script.index("echo [4/5]"):script.index("echo [5/5]")]
    scripts = root / "scripts"
    scripts.mkdir()
    for name in ("prepare_release_assets.py", "release_metadata.py"):
        source = ROOT / "scripts" / name
        if source.exists():
            shutil.copyfile(source, scripts / name)
    wrapper = root / "prepare-assets.cmd"
    wrapper.write_text("@echo off\nsetlocal\n" + stage + "\nexit /b 0\n", encoding="ascii")
    destination = (root / "Output" / f"Clipboard.Bridge.Release.V{VERSION}").resolve()
    # The old stage contains recursive deletion: prove its target is test-owned first.
    assert destination.is_relative_to(root.resolve())
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)
    environment = os.environ.copy()
    environment.update(VERSION=VERSION, PYTHON_EXE=sys.executable)
    return subprocess.run(["cmd.exe", "/d", "/c", "call", str(wrapper)], cwd=root,
                          env=environment, capture_output=True, timeout=30)


@pytest.mark.skipif(sys.platform != "win32", reason="Executes the actual Windows batch stage")
def test_batch_preparation_preserves_previously_added_assets(tmp_path):
    root = tmp_path / "project with spaces"
    destination, extra = release_fixture(root)
    result = run_batch_preparation(root)
    assert result.returncode == 0, result.stderr
    assert extra.exists(), "Preparation deleted a pre-existing ARM64 package"
    assert extra.read_bytes() == b"must remain untouched"
    assert (destination / "iPhone.Load.Clipboard.shortcut").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Executes the actual Windows batch stage")
def test_batch_preparation_missing_shortcut_fails_before_replacing_existing_assets(tmp_path):
    root = tmp_path / "project"
    destination, extra = release_fixture(root)
    previous = destination / f"Clipboard.Bridge.Portable.Windows.x64.V{VERSION}.exe"
    previous.write_bytes(b"previous build must survive")
    (root / "Iphone Shortcuts/Load Clipboard.shortcut").unlink()
    result = run_batch_preparation(root)
    assert result.returncode != 0, "A missing shortcut was incorrectly reported as success"
    assert extra.read_bytes() == b"must remain untouched"
    assert previous.read_bytes() == b"previous build must survive"


@pytest.mark.skipif(sys.platform != "win32", reason="Executes the actual Windows batch stage")
def test_batch_preparation_uses_the_actual_android_build_version(tmp_path):
    root = tmp_path / "project"
    destination, _ = release_fixture(root)
    add_apk(root)
    result = run_batch_preparation(root)
    assert result.returncode == 0, result.stderr
    assert (destination / "Clipboard.Bridge.Android.universal.V1.0.0-beta.12.apk").exists()
