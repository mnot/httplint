"""
Wire-derived values interpolated into hand-built Markdown must not be able to
end the surrounding code span (via a backtick or any line break) and so
smuggle raw HTML into note.detail.
"""

import unittest

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


class InlineSafeTest(unittest.TestCase):
    def test_strips_backtick_nul_and_line_breaks(self) -> None:
        raw = "a`b\x00c\nd\re\x0bf\x0cg\x1ch\x1di\x1ej\x85k l m"
        self.assertEqual(inline_safe(raw), "abcdefghijklm")

    def test_markdown_list_items_stay_single_line(self) -> None:
        out = markdown_list(["a\nb`c", "d e"])
        self.assertEqual(str(out), "- abc\n- de")


if __name__ == "__main__":
    unittest.main()
