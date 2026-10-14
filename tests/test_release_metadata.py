import importlib.util
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

    assert version == "2.0.11"
    metadata.validate(version)


def test_installer_default_matches_project_version():
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    installer = (ROOT / "Clipboard_Bridge_setup.iss").read_text(encoding="utf-8")

    assert f'#define MyAppVersion "{version}"' in installer


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
