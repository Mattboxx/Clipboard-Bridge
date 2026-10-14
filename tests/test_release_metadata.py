import importlib.util
import re
from html.parser import HTMLParser
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

    assert version == "2.0.13"
    metadata.validate(version)


def test_installer_default_matches_project_version():
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    installer = (ROOT / "Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")

    assert f'#define MyAppVersion "{version}"' in installer


def test_installer_supports_native_arm64_without_changing_app_identity():
    installer = (ROOT / "Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")
    assert '#define MyAppArchitecture "x64"' in installer
    assert '#if MyAppArchitecture == "arm64"' in installer
    assert "ArchitecturesAllowed=arm64" in installer
    assert "ArchitecturesAllowed=x64compatible" in installer
    assert "setup_{#MyAppArchitecture}_V{#MyAppVersion}" in installer
    assert installer.count("AppId=") == 1


def test_website_support_opens_donation_directly_and_stylesheet_exists():
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
    assert link["href"] == "https://ko-fi.com/mattboxx"
    assert link["target"] == "_blank"
    assert {"noopener", "noreferrer"} <= set(link["rel"].split())
    assert links.stylesheets == ["site.css"]
    assert (ROOT / "docs/site.css").is_file()


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
                self.images.append(values["src"])
                assert "alt" in values
            if tag == "a" and "/releases/download/" in values.get("href", ""):
                self.downloads.add(values["href"].rsplit("/", 1)[1])
            if tag == "main":
                self.main_ids.append(values.get("id"))

    assets = Assets()
    assets.feed((ROOT / "docs/index.html").read_text(encoding="utf-8"))
    assert assets.main_ids == ["main"]
    assert assets.images
    for source in assets.images:
        assert not source.startswith(("http:", "https:")), "Website assets should work without a CDN"
        assert (ROOT / "docs" / source).is_file(), source
    version = load_release_metadata().current_version()
    for architecture in ("x64", "arm64"):
        assert f"Clipboard.Bridge.Portable.Windows.{architecture}.V{version}.exe" in assets.downloads
        assert f"Clipboard.Bridge_windows_client_and_server_setup_{architecture}_V{version}.exe" in assets.downloads
    assert {"iPhone.Load.Clipboard.shortcut", "iPhone.Download.Clipboard.shortcut"} <= assets.downloads
    assert "Clipboard.Bridge.Android.universal.V1.0.0-beta.10.apk" in assets.downloads
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
    build = (ROOT / "build_windows_release.bat").read_text(encoding="utf-8")
    attachments = build.split("Preparing the public GitHub release assets...", 1)[1]
    assert ".py" not in attachments
