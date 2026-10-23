"""
Wire-derived values interpolated into hand-built Markdown must not be able to
end the surrounding code span (via a backtick or any line break) and so
smuggle raw HTML into note.detail.
"""

import unittest

from markdown import Markdown

from httplint.message import HttpResponseLinter
from httplint.util import inline_safe, markdown_list

# Characters that str.splitlines() (and so some Markdown parsers) treat as
# line breaks, as percent-encoded Structured Field display-string bytes.
LINE_BREAKS = [
    "%0a",
    "%0d",
    "%0d%0a",
    "%0b",
    "%0c",
    "%1c",
    "%1d",
    "%1e",
    "%c2%85",
    "%e2%80%a8",
    "%e2%80%a9",
]
HTML = "<img src=x onerror=alert(1)>"


def detail_text(field_name: bytes, field_value: bytes) -> str:
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(field_name, field_value)])
    linter.finish_content(True)
    return "\n".join(str(n.detail) for n in linter.notes)


class SfParamInjectionTest(unittest.TestCase):
    def check(self, name: bytes, prefix: bytes, param: bytes) -> None:
        for sep in LINE_BREAKS:
            payload = f'%"x{sep}{sep}{HTML}{sep}{sep}`"'
            with self.subTest(field=name, param=param, sep=sep):
                value = prefix + b"; " + param + b"=" + payload.encode("ascii")
                detail = detail_text(name, value)
                self.assertNotIn("<img", detail)
                self.assertIn("&lt;img", detail)

    def test_cache_status_params(self) -> None:
        for param in (b"detail", b"key", b"fwd", b"foo"):
            self.check(b"Cache-Status", b"c", param)

    def test_proxy_status_params(self) -> None:
        for param in (b"details", b"error", b"foo"):
            self.check(b"Proxy-Status", b"p", param)


class CharsetInjectionTest(unittest.TestCase):
    def test_unknown_charset_in_content_type(self) -> None:
        # Only a name that isn't a known label reaches CHARSET_UNKNOWN's text, and any
        # quoted-string can be one. 0x85 is an obs-text line break to some parsers.
        for sep in ("", "\x85", "\xa0"):
            payload = f'text/plain; charset="x{sep}`{HTML}`{sep}"'
            with self.subTest(sep=sep):
                detail = detail_text(b"Content-Type", payload.encode("latin-1"))
                self.assertNotIn("<img", detail)
                self.assertIn("&lt;img", detail)


class OtherSitesInjectionTest(unittest.TestCase):
    def test_link_resource_hint_target(self) -> None:
        # Exploitable before inline_safe handled line breaks.
        for sep in ("\n", "\r", "\r\n", "\u2028"):
            with self.subTest(sep=repr(sep)):
                value = f"<http://a/x{sep}{sep}{HTML}{sep}{sep}`>; rel=preload"
                detail = detail_text(b"Link", value.encode("utf-8"))
                self.assertNotIn("<img", detail)

    def test_set_cookie_hardened_name(self) -> None:
        # Hardening: names are limited by the cookie parser, so this is
        # not known to be reachable.
        value = f"a{HTML}`=b; Secure; HttpOnly; SameSite=Strict; Path=/"
        self.assertNotIn("<img", detail_text(b"Set-Cookie", value.encode("utf-8")))


class EmptyCodeSpanTest(unittest.TestCase):
    """
    A hand-built code span whose content is empty ends up as two adjacent
    backticks, which Markdown reads as an opener that closes at the *next*
    backtick -- turning a later span's value into bare, unescaped prose.
    Wire values that are empty (or that inline_safe strips to empty) must
    never produce one.
    """

    def check_escaped(self, detail: str) -> None:
        self.assertNotIn("<img", detail)
        self.assertIn("&lt;img", detail)

    def test_proxy_status_empty_target(self) -> None:
        for target in ('""', '"`"', '"``"'):
            for param in ("details", "next-hop", "error", "foo"):
                with self.subTest(target=target, param=param):
                    value = f'{target}; {param}="{HTML}"'
                    self.check_escaped(detail_text(b"Proxy-Status", value.encode("ascii")))

    def test_proxy_status_empty_target_among_others(self) -> None:
        value = f'a; details="x", ""; details="{HTML}", b; details="{HTML}"'
        self.check_escaped(detail_text(b"Proxy-Status", value.encode("ascii")))

    def test_proxy_status_empty_param_value(self) -> None:
        for empty in ('""', '"`"', '"``"'):
            for first in ("foo", "bar", "error=dns_error", "next-hop", "received-status=200"):
                for second in ("details", "next-hop", "bar", "key"):
                    with self.subTest(empty=empty, first=first, second=second):
                        name, _, val = first.partition("=")
                        head = f"{name}={val}" if val else f"{name}={empty}"
                        value = f'a; {head}; {second}="{HTML}"'
                        self.check_escaped(detail_text(b"Proxy-Status", value.encode("ascii")))

    def test_set_cookie_hardened_nameless(self) -> None:
        hardened = "Secure; HttpOnly; SameSite=Lax"
        # Cookie names can't contain "=" or ";", so the payload can't use HTML.
        payload = "<script>alert(1)</script>"
        named = f"{payload}=1; {hardened}"
        escaped = "<code>&lt;script&gt;alert(1)&lt;/script&gt;</code>"
        for first, second, nameless in (
            (f"foo; {hardened}", named, True),
            (named, f"foo; {hardened}", True),
            (f"`=1; {hardened}", named, True),
            (f"foo; {hardened}", f"bar; {hardened}", True),
            (f"bar=1; {hardened}", named, False),
        ):
            with self.subTest(first=first, second=second):
                linter = HttpResponseLinter()
                linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
                linter.process_headers(
                    [
                        (b"Set-Cookie", first.encode("utf-8")),
                        (b"Set-Cookie", second.encode("utf-8")),
                    ]
                )
                linter.finish_content(True)
                detail = "\n".join(
                    str(n.detail) for n in linter.notes if "HARDENED" in n.__class__.__name__
                )
                self.assertNotIn("<script", detail)
                self.assertNotIn("``", detail)
                if named in (first, second):
                    self.assertIn(escaped, detail)
                self.assertEqual("(empty)" in detail, nameless)

    # Known bug, tracked in https://github.com/mnot/httplint/issues/276.
    # Remove expectedFailure when that issue is fixed.
    @unittest.expectedFailure
    def test_cache_status_empty_target(self) -> None:
        for param in ("detail", "key"):
            with self.subTest(param=param):
                value = f'""; {param}="{HTML}"'
                detail = detail_text(b"Cache-Status", value.encode("ascii"))
                self.check_escaped(detail)
                # Separating the bullets from the target line stopped the escaping failure,
                # but an empty target still renders as an empty code span.
                self.assertNotIn("``", detail)

    # Known bug, tracked in https://github.com/mnot/httplint/issues/277.
    # Remove expectedFailure when that issue is fixed.
    @unittest.expectedFailure
    def test_link_resource_hint_empty_target(self) -> None:
        # A bracketed target ends at the first ">", so the HTML goes in an unbracketed one.
        value = f"<>; rel=preload, x{HTML}; rel=preload"
        self.check_escaped(detail_text(b"Link", value.encode("ascii")))
        self.assertNotIn("``", detail_text(b"Link", b"<>; rel=preload"))


class InlineSafeTest(unittest.TestCase):
    def test_strips_backtick_nul_and_line_breaks(self) -> None:
        raw = "a`b\x00c\nd\re\x0bf\x0cg\x1ch\x1di\x1ej\x85k l m"
        self.assertEqual(inline_safe(raw), "abcdefghijklm")

    def test_markdown_list_items_stay_single_line(self) -> None:
        out = markdown_list(["a\nb`c", "d e"])
        self.assertEqual(str(out), "- abc\n- de")

    def test_markdown_list_empty_items_render_escaped(self) -> None:
        out = markdown_list(["`", HTML, ""], markup="`")
        self.assertEqual(str(out), f"- ``\n- `{HTML}`\n- ``")
        html = Markdown(output_format="html").convert(str(out))
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)


if __name__ == "__main__":
    unittest.main()
