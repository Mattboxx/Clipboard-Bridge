import importlib.util
import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE = "https://mattboxx.github.io/Clipboard-Bridge/"
PAGES = ("index.html", "tutorial.html", "tutorial.it.html",
         "windows-iphone-clipboard.html", "apple-android-clipboard.html")


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.texts = []
        self.title = ""
        self.json_ld = []
        self._in_title = False
        self._in_json = False
        self._json = ""
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == "title":
            self._in_title = True
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._in_json = True
            self._json = ""

    def handle_data(self, data):
        self.texts.append(data)
        if self._in_title:
            self.title += data
        if self._in_json:
            self._json += data

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_json:
            self.json_ld.append(json.loads(self._json))
            self._in_json = False

    def tags(self, name):
        return [attrs for tag, attrs in self.elements if tag == name]


def read_page(filename):
    return Page((DOCS / filename).read_text(encoding="utf-8"))


def test_every_public_page_has_distinct_search_metadata():
    titles, descriptions = [], []
    for filename in PAGES:
        page = read_page(filename)
        titles.append(page.title)
        descriptions.append(next(m["content"] for m in page.tags("meta")
                                 if m.get("name") == "description"))
        assert len(page.tags("title")) == len(page.tags("h1")) == 1
        assert all(m.get("content", "").lower().find("noindex") == -1
                   for m in page.tags("meta") if m.get("name") == "robots")
        canonical = [link["href"] for link in page.tags("link")
                     if link.get("rel") == "canonical"]
        assert canonical == [BASE + ("" if filename == "index.html" else filename)]
        language = "it" if filename == "tutorial.it.html" else "en"
        assert page.tags("html")[0]["lang"] == language
        assert page.json_ld
    assert len(set(titles)) == len(PAGES)
    assert len(set(descriptions)) == len(PAGES)


@pytest.mark.parametrize("filename", PAGES)
def test_local_links_fragments_and_assets_exist(filename):
    page = read_page(filename)
    current_url = urljoin(BASE, filename)
    for tag, attrs in page.elements:
        for attr in ("href", "src", "poster"):
            if attr not in attrs:
                continue
            target_url = urljoin(current_url, attrs[attr])
            if not target_url.startswith(BASE):
                continue
            parsed = urlsplit(target_url)
            relative = unquote(parsed.path.removeprefix(urlsplit(BASE).path)) or "index.html"
            target = DOCS / relative
            assert target.is_file(), f"{filename}: missing {tag} {attrs[attr]}"
            if parsed.fragment and target.suffix == ".html":
                target_page = page if target.name == filename else read_page(relative)
                ids = {values.get("id") for _, values in target_page.elements}
                assert unquote(parsed.fragment) in ids, f"{filename}: missing #{parsed.fragment}"


def test_sitemap_covers_public_pages_and_uses_real_dates():
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap = ET.parse(DOCS / "sitemap.xml")
    urls = sitemap.findall("sm:url", ns)
    locations = [entry.findtext("sm:loc", namespaces=ns) for entry in urls]
    assert set(locations) == {BASE + ("" if p == "index.html" else p) for p in PAGES}
    assert len(locations) == len(set(locations))
    for entry in urls:
        assert date.fromisoformat(entry.findtext("sm:lastmod", namespaces=ns)) <= date.today()


def test_tutorial_translations_are_reciprocal_not_fake_alternates():
    expected = {("en", BASE + "tutorial.html"), ("it", BASE + "tutorial.it.html")}
    for filename in ("tutorial.html", "tutorial.it.html"):
        assert {(a["hreflang"], a["href"]) for a in read_page(filename).tags("link")
                if a.get("rel") == "alternate"} == expected
    for filename in ("windows-iphone-clipboard.html", "apple-android-clipboard.html"):
        assert not any(a.get("rel") == "alternate" for a in read_page(filename).tags("link"))


def test_structured_data_identifies_the_project_without_fake_reviews():
    graph = read_page("index.html").json_ld[0]["@graph"]
    app = next(node for node in graph if node["@type"] == "SoftwareApplication")
    assert app["@id"] == BASE + "#software"
    assert app["sameAs"] == "https://github.com/Mattboxx/Clipboard-Bridge"
    assert app["operatingSystem"] == ["Windows", "Android"]
    assert app["offers"]["price"] == "0"
    assert "user-triggered Apple Shortcuts" in app["description"]
    for filename in PAGES:
        schema = json.dumps(read_page(filename).json_ld)
        assert "aggregateRating" not in schema
        assert '"review"' not in schema
        if filename != "index.html":
            assert BASE + "#software" in schema


def test_english_guides_explain_the_quick_iphone_workflow_and_limits():
    for filename in ("windows-iphone-clipboard.html", "apple-android-clipboard.html"):
        page = read_page(filename)
        visible = " ".join(page.texts)
        assert "Control Center" in visible and "Share Sheet" in visible
        assert "user-triggered" in visible or "run Send or Receive" in visible
        assert "5088/clipboard/latest/raw" in visible
        assert "private VPN" in visible
        assert "optional" in visible and "readable" in visible
        assert 'href="' + filename + '"' in (DOCS / "index.html").read_text(encoding="utf-8")
        assert filename in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "windows-iphone-workflow" not in " ".join(
        (DOCS / filename).read_text(encoding="utf-8") for filename in PAGES)


def load_notifier():
    spec = importlib.util.spec_from_file_location("search_notifier", ROOT / "scripts/notify_search_engines.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_indexnow_payload_is_limited_to_public_project_pages():
    notifier = load_notifier()
    payload = notifier.build_payload()
    assert payload["host"] == "mattboxx.github.io"
    assert payload["keyLocation"] == BASE + notifier.KEY + ".txt"
    assert len(payload["urlList"]) == len(PAGES)
    assert all(url.startswith(BASE) and "?" not in url for url in payload["urlList"])


@pytest.mark.parametrize("url", ["http://192.168.1.50:5088/", "https://example.com/",
                                 BASE + "tutorial.html?token=private", BASE + "../secret.html",
                                 BASE + "missing.html", BASE + "#download"])
def test_indexnow_rejects_nonpublic_or_missing_urls(tmp_path, url):
    notifier = load_notifier()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / f"{notifier.KEY}.txt").write_text(notifier.KEY, encoding="utf-8")
    (docs / "sitemap.xml").write_text(
        f'<urlset xmlns="{notifier.NS["sm"]}"><url><loc>{url}</loc></url></urlset>',
        encoding="utf-8")
    with pytest.raises(ValueError, match="Not a public project HTML page"):
        notifier.build_payload(tmp_path)


@pytest.mark.parametrize("status", [200, 202])
def test_indexnow_submission_verifies_key_before_posting(monkeypatch, status):
    notifier = load_notifier()
    calls = []

    class Response:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return notifier.KEY.encode()

    def open_url(request, timeout):
        calls.append(request)
        return Response(200 if isinstance(request, str) else status)

    monkeypatch.setattr(notifier.urllib.request, "urlopen", open_url)
    payload = notifier.build_payload()
    assert notifier.submit(payload) == status
    assert calls[0] == payload["keyLocation"]
    assert calls[1].full_url == notifier.ENDPOINT
    assert calls[1].get_method() == "POST"
    assert json.loads(calls[1].data) == payload


def test_indexnow_does_not_submit_when_live_key_differs(monkeypatch):
    notifier = load_notifier()
    calls = []

    class WrongKey:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return b"not the deployed key"

    def open_url(request, timeout):
        calls.append(request)
        return WrongKey()

    monkeypatch.setattr(notifier.urllib.request, "urlopen", open_url)
    with pytest.raises(ValueError, match="live key"):
        notifier.submit(notifier.build_payload())
    assert len(calls) == 1
