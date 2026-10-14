import pytest

from clipboard_text import decode_rtf_bytes, plain_clipboard_text


@pytest.mark.parametrize("text", [
    "", "  Caff\u00e8 \U0001f600\r\n\t\u96ea\r\n  ",
    "\U0001f469\u200d\U0001f4bb \u2764\ufe0f \U0001f44d\U0001f3fd \U0001f1ee\U0001f1f9",
    r"An example: {\rtf1\b not a complete clipboard document}",
    r"{\rtfoo this is ordinary text}",
])
def test_plain_unicode_text_is_not_changed(text):
    assert plain_clipboard_text(text) == text


@pytest.mark.parametrize("rtf,expected", [
    (r"{\rtf1\ansi\ansicpg1252   Caff\'e8 \b bold\b0\par\tab fine  }",
     "  Caff\u00e8 bold\n\tfine  "),
    (r"{\rtf1\ansi\uc1 \u-10179?\u-8704?}", "\U0001f600"),
    (r"{\rtf1\ansi\uc1 \u-10179?\u-9111?\u8205?\u-10179?\u-9029? \u10084?\u-497?}",
     "\U0001f469\u200d\U0001f4bb \u2764\ufe0f"),
    (r"{\rtf1\uc0 \u-10179\u-8704\line\u38634}", "\U0001f600\n\u96ea"),
    (r"{\rtf1\uc2 \u233?? \u-10179??\u-8704??}", "\u00e9 \U0001f600"),
    (r"{\rtf1{\fonttbl{\f0\fnil Helvetica;}}{\colortbl;\red255\green0\blue0;}\f0 visible}",
     "visible"),
    (r'{\rtf1{\field{\*\fldinst{HYPERLINK "https://example.com"}}{\fldrslt Open here}}}',
     "Open here"),
    (r"{\rtf1 literal \\fldinst \{braces\} \\path}", r"literal \fldinst {braces} \path"),
    ("\ufeff\r\n" + r"{\rtf1 Hello}", "Hello"),
])
def test_rtf_preserves_visible_text_and_unicode(rtf, expected):
    actual = plain_clipboard_text(rtf)
    assert actual == expected
    assert actual.encode("utf-8").decode("utf-8") == expected


def test_bad_unicode_control_does_not_discard_clipboard():
    text = r"{\rtf1\u9999999999?}"
    assert plain_clipboard_text(text) == text


@pytest.mark.parametrize("encoding,page,text", [
    ("cp1252", 1252, "Caff\u00e8 \u201cquoted\u201d"),
    ("cp1251", 1251, "\u041f\u0440\u0438\u0432\u0435\u0442"),
    ("utf-8", 65001, "\u96ea \U0001f600"),
])
def test_rtf_bytes_honor_the_declared_codepage(encoding, page, text):
    raw = ("{\\rtf1\\ansi\\ansicpg" + str(page) + " " + text + "}").encode(encoding)
    assert plain_clipboard_text(decode_rtf_bytes(raw)) == text


def test_non_rtf_bytes_are_not_decoded_as_rtf():
    assert decode_rtf_bytes(b"plain text") is None
