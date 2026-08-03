import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_release_metadata():
    source = ROOT / "scripts" / "release_metadata.py"
    spec = importlib.util.spec_from_file_location("release_metadata_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_metadata_is_consistent():
    metadata = load_release_metadata()
    version = metadata.current_version()

    assert version == "2.0.6"
    metadata.validate(version)


def test_installer_default_matches_project_version():
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    installer = (ROOT / "Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")

    assert f'#define MyAppVersion "{version}"' in installer
