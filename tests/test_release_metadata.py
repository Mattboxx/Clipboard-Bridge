import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def load_release_metadata():
    source = ROOT / "scripts" / "release_metadata.py"
    spec = importlib.util.spec_from_file_location("release_metadata_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_component_versions_match_docs_and_catalog_mirror():
    server_source = (ROOT / "clipboard_bridge-Server.py").read_text(encoding="utf-8")
    server = re.search(r'^SERVER_VERSION = "([0-9.]+)"', server_source, re.M).group(1)
    android_source = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    android = re.search(r'versionName = "([^"]+)"', android_source).group(1)
    for filename in ("README.md", "README.it.md", "docs/index.html",
                     "docs/tutorial.html", "docs/tutorial.it.html", "maintainer/TUTORIAL_DEVTO.md"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        assert f"clipboard-bridge-server:{server}" in text
        assert f"Clipboard.Bridge.Android.universal.V{android}.apk" in text
        assert f"/releases/download/android-v{android}/" in text
    catalog = ROOT / "distribution/clipboard-bridge-store"
    for filename in ("compose.yaml", "Apps/ClipboardBridge/docker-compose.yml",
                     ".github/workflows/validate.yml",
                     "clipboard-bridge/docker-compose.yml",
                     "adapters/umbrel/clipboard-bridge/docker-compose.yml",
                     "adapters/runtipi/apps/clipboard-bridge/docker-compose.yml"):
        assert f"clipboard-bridge-server:{server}" in (catalog / filename).read_text(encoding="utf-8")


def test_release_metadata_is_consistent():
    metadata = load_release_metadata()
    version = metadata.current_version()

    assert version == "2.0.20"
    metadata.validate(version)


@pytest.mark.parametrize("manifest,name,patched,obsolete,next_major", [
    ("requirements-server.txt", "flask", "3.1.3", ("3.1", "3.1.1", "3.1.2"), "4"),
    ("requirements-client.txt", "requests", "2.33.0", ("2.32", "2.32.4", "2.32.5"), "3"),
    ("requirements-client.txt", "pillow", "12.3.0", ("11", "12.1.1", "12.2.0"), "13"),
])
def test_reviewed_security_floors_exclude_obsolete_versions(manifest, name, patched, obsolete, next_major):
    requirements = [Requirement(line) for line in (ROOT / manifest).read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    requirement = next(item for item in requirements if item.name.lower() == name)
    floors = [Version(spec.version) for spec in requirement.specifier if spec.operator in (">=", "==")]
    assert floors and max(floors) >= Version(patched)
    assert max(floors) in requirement.specifier
    assert all(version not in requirement.specifier for version in obsolete)
    assert next_major not in requirement.specifier


def test_installer_default_matches_project_version():
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    installer = (ROOT / "packaging/windows/Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")

    assert f'#define MyAppVersion "{version}"' in installer


def test_windows_packaging_paths_are_relative_to_repository_root():
    installer = (ROOT / "packaging/windows/Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")
    assert "SourceDir=..\\.." in installer
    assert "OutputDir=Output" in installer
    assert 'Source: "dist\\Clipboard Bridge.exe"' in installer
    for name in ("build_client.bat", "build_release.bat"):
        script = (ROOT / "scripts/windows" / name).read_text(encoding="utf-8")
        assert 'cd /d "%~dp0..\\.."' in script
        assert "--version-file packaging\\windows\\windows_version_info.txt" in script
        assert "--copy-metadata striprtf" in script
    release = (ROOT / "scripts/windows/build_release.bat").read_text(encoding="utf-8")
    assert '"packaging\\windows\\Clipboard_Bridge_setup.iss"' in release
    workflow = (ROOT / ".github/workflows/windows-arm64.yml").read_text(encoding="utf-8")
    assert '"packaging/windows/**"' in workflow
    assert "--version-file packaging/windows/windows_version_info.txt" in workflow
    assert "/OOutput/arm64 packaging/windows/Clipboard_Bridge_setup.iss" in workflow
    for old in ("build_client.bat", "build_windows_release.bat",
                "Clipboard_Bridge_setup.iss", "windows_version_info.txt"):
        assert not (ROOT / old).exists()


def test_developer_navigation_links_resolve_after_repository_reorganization():
    files = ("docs/development/ARCHITECTURE.md", "scripts/README.md",
             "packaging/windows/README.md", "CONTRIBUTING.md")
    for name in files:
        document = ROOT / name
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("#"):
                continue
            path, _, fragment = link.partition("#")
            target = (document.parent / path).resolve()
            assert target.is_file(), f"{name}: broken link {link}"
            if fragment:
                headings = re.findall(r"^#+ (.+)$", target.read_text(encoding="utf-8"), re.MULTILINE)
                slugs = {re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
                         for heading in headings}
                assert fragment in slugs, f"{name}: missing heading {link}"


def test_docker_context_is_an_explicit_server_only_allowlist():
    rules = [line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert rules[0] == "*"
    assert set(rules[1:]) == {
        "!Dockerfile", "!requirements-server.txt", "!clipboard_bridge-Server.py",
        "!clipboard_text.py", "!clipboard_storage.py", "!server_web_strings.json", "!LICENSE",
    }
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY clipboard_text.py ." in dockerfile and "COPY LICENSE ." in dockerfile
    assert "COPY clipboard_storage.py ." in dockerfile
    assert "COPY server_web_strings.json ." in dockerfile


def test_installer_supports_native_arm64_without_changing_app_identity():
    installer = (ROOT / "packaging/windows/Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")
    assert '#define MyAppArchitecture "x64"' in installer
    assert '#if MyAppArchitecture == "arm64"' in installer
    assert "ArchitecturesAllowed=arm64" in installer
    assert "ArchitecturesAllowed=x64compatible" in installer
    assert "setup_{#MyAppArchitecture}_V{#MyAppVersion}" in installer
    assert installer.count("AppId=") == 1


def test_windows_builds_use_the_same_pinned_toolchain():
    pin = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert re.search(r"(?m)^pyinstaller==\d+\.\d+\.\d+$", pin)
    for name in ("build_client.bat", "build_release.bat"):
        script = (ROOT / "scripts/windows" / name).read_text(encoding="utf-8")
        assert "-m pip install -r requirements-build.txt" in script
        assert "--upgrade pyinstaller" not in script
        assert 'if not defined PYTHON_EXE (' in script
        assert '%VIRTUAL_ENV%\\Scripts\\python.exe' in script
    arm = (ROOT / ".github/workflows/windows-arm64.yml").read_text(encoding="utf-8")
    x64 = (ROOT / ".github/workflows/windows-x64.yml").read_text(encoding="utf-8")
    for workflow in (arm, x64):
        assert '"requirements-build.txt"' in workflow
        assert "-r requirements-build.txt pytest" in workflow
    assert 'cmd /d /c scripts\\windows\\build_release.bat' in x64
    assert '--architecture x64 --smoke' in x64
    assert 'Installer changed $name' in x64
    assert 'Installer payload mismatch' in x64
    assert 'Get-AuthenticodeSignature' in x64
    assert 'clipboard-bridge-windows-x64' in x64


def test_x64_build_provenance_uses_compiler_output_and_identifies_pr_source():
    workflow = (ROOT / ".github/workflows/windows-x64.yml").read_text(encoding="utf-8")
    assert "VersionInfo.ProductVersion" not in workflow
    assert "Tee-Object -FilePath Output/x64-build.log" in workflow
    assert "Compiler engine version:" in workflow
    assert "Could not identify the Inno Setup compiler version" in workflow
    assert "source_commit = (git rev-parse HEAD)" in workflow
    assert "pull_request_head = $env:PR_HEAD_SHA" in workflow
    assert "workflow_commit = $env:GITHUB_SHA" in workflow
    assert "${{ github.event.pull_request.head.sha }}" in workflow


def test_website_support_opens_platform_choice_and_stylesheet_exists():
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.support = []
            self.stylesheets = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "a" and "support-nav" in values.get("class", "").split():
                self.support.append(values)
            if tag == "link" and values.get("rel") == "stylesheet":
                self.stylesheets.append(values["href"])

    links = Links()
    links.feed((ROOT / "docs/index.html").read_text(encoding="utf-8"))
    assert len(links.support) == 1
    link = links.support[0]
    assert link["href"] == "#support"
    assert "data-support-open" in link
    script = (ROOT / "docs/site.js").read_text(encoding="utf-8")
    assert 'trigger.setAttribute("aria-haspopup", "dialog")' in script
    assert 'trigger.setAttribute("aria-controls", dialog.id)' in script
    assert "https://ko-fi.com/mattboxx" in script
    assert "https://github.com/sponsors/Mattboxx" in script
    assert "dialog.showModal()" in script and "dialog.close()" in script
    assert links.stylesheets == ["site.css", "apple-shortcuts.css", "bridge-ui.css", "home-cover.css"]
    assert all((ROOT / "docs" / source).is_file() for source in links.stylesheets)
    design = (ROOT / "docs/bridge-ui.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in design
    assert 'url("assets/windows-history-wide.png")' in design
    assert (ROOT / "docs/assets/windows-history-wide.png").is_file()


def test_sponsorship_links_are_available_in_both_readmes_and_github_funding():
    for name in ("README.md", "README.it.md"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "https://ko-fi.com/mattboxx" in source
        assert "https://github.com/sponsors/Mattboxx" in source
    funding = (ROOT / ".github/FUNDING.yml").read_text(encoding="utf-8")
    assert "github: [Mattboxx]" in funding
    assert "ko_fi: mattboxx" in funding


def test_website_local_images_and_device_downloads_exist():
    class Assets(HTMLParser):
        def __init__(self):
            super().__init__()
            self.images = []
            self.downloads = set()
            self.main_ids = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "img":
                self.images.append(values)
                assert "alt" in values
            if tag == "a" and "/releases/download/" in values.get("href", ""):
                self.downloads.add(values["href"].rsplit("/", 1)[1])
            if tag == "main":
                self.main_ids.append(values.get("id"))

    assets = Assets()
    assets.feed((ROOT / "docs/index.html").read_text(encoding="utf-8"))
    assert assets.main_ids == ["main"]
    assert assets.images
    for image in assets.images:
        source = image["src"]
        if source.startswith("https://help.apple.com/assets/"):
            assert "data-apple-image" in image
            assert image["referrerpolicy"] == "no-referrer"
        else:
            assert not source.startswith(("http:", "https:")), "Only credited Apple illustrations may use a CDN"
            assert (ROOT / "docs" / source).is_file(), source
    version = load_release_metadata().current_version()
    for architecture in ("x64", "arm64"):
        assert f"Clipboard.Bridge.Portable.Windows.{architecture}.V{version}.exe" in assets.downloads
        assert f"Clipboard.Bridge_windows_client_and_server_setup_{architecture}_V{version}.exe" in assets.downloads
    assert {"iPhone.Load.Clipboard.shortcut", "iPhone.Download.Clipboard.shortcut"} <= assets.downloads
    assert "Clipboard.Bridge.Android.universal.V1.0.0-beta.12.apk" in assets.downloads
    assert (ROOT / "docs/assets/icons/LICENSE").is_file()


def test_website_highlights_stable_server_and_windows_alternative():
    class ServerInfo(HTMLParser):
        def __init__(self):
            super().__init__()
            self.details = 0
            self.server_visible = False
            self.command_visible = False

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "details":
                self.details += 1
            if values.get("id") == "server":
                self.server_visible = self.details == 0
            if values.get("id") == "image-command":
                self.command_visible = self.details == 0

        def handle_endtag(self, tag):
            if tag == "details":
                self.details -= 1

    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    info = ServerInfo()
    info.feed(html)
    assert info.server_visible and info.command_visible
    docker = (ROOT / "DOCKER.md").read_text(encoding="utf-8")
    stable_image = re.search(r"ghcr.io/mattboxx/clipboard-bridge-server:\d+\.\d+\.\d+", docker).group()
    assert f"docker pull {stable_image}" in html
    assert 'href="#server">Get the server' in html
    assert "Your Windows PC can do the job." in html
    assert "Server mode" in html
    assert (ROOT / "docs/site.js").is_file()


def test_network_guidance_is_visible_and_links_to_the_guide():
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert 'id="network"' in html
    assert "Same local network. Or a private VPN." in html
    assert "subnet router" in html
    assert "Clipboard Bridge does not enable it automatically" in html
    assert "GUIDE.md#local-network-vpn-and-subnet-routing" in html
    for file in ("README.md", "README.it.md"):
        assert "GUIDE.md#local-network-vpn-and-subnet-routing" in (ROOT / file).read_text(encoding="utf-8")
    assert "### Local network, VPN and subnet routing" in (ROOT / "GUIDE.md").read_text(encoding="utf-8")


def test_python_sources_are_developer_only_not_release_downloads():
    for filename in ("README.md", "README.it.md", "GUIDE.md", "docs/index.html"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        assert not re.search(r"/releases/download/[^\s\"<>)]*\.py(?:[\"<>)]|\s|$)", text), filename
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "For developers:" in html
    assert "Download Python server" not in html
    for source in ("clipboard_bridge-Server.py", "clipboard_bridge_windows.py"):
        assert f"/blob/main/{source}" in html
    build = (ROOT / "scripts/windows/build_release.bat").read_text(encoding="utf-8")
    attachments = build.split("echo [4/5]", 1)[1]
    assert 'scripts\\prepare_release_assets.py --version "%VERSION%"' in attachments
    assert not re.search(r"(?im)^copy\s+.*\.py(?:\s|\")", attachments)
