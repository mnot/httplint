import unittest
from typing import List

from httplint.field.tests import FakeRequestLinter, FakeResponseLinter
from httplint.field.utils import is_secure, resolve_url
from httplint.message import HttpMessageLinter


class ResolveUrlTest(unittest.TestCase):
    def test_relative(self) -> None:
        resolved = resolve_url("../c", "https://example.com/a/b")
        assert resolved is not None
        self.assertEqual(resolved.geturl(), "https://example.com/c")

    def test_empty_base(self) -> None:
        resolved = resolve_url("http://example.com/x")
        assert resolved is not None
        self.assertEqual(resolved.netloc, "example.com")

    def test_malformed_ipv6(self) -> None:
        for url in ("http://[", "http://[::1", "http://[::1]x"):
            self.assertIsNone(resolve_url(url))
            self.assertIsNone(resolve_url(url, "https://example.com/"))

    def test_is_secure(self) -> None:
        for url, secure in [
            ("https://example.com/", True),
            ("WSS://example.com/", True),
            ("http://example.com/", False),
            ("ws://example.com/", False),
            ("/relative", False),
        ]:
            resolved = resolve_url(url)
            assert resolved is not None
            self.assertEqual(is_secure(resolved), secure, url)


class NoteCountTest(unittest.TestCase):
    "An unresolvable URL is reported once, and without BAD_SYNTAX."

    @staticmethod
    def note_names(linter: HttpMessageLinter) -> List[str]:
        return [n.__class__.__name__ for n in linter.notes]

    @staticmethod
    def response(name: bytes, value: bytes) -> FakeResponseLinter:
        linter = FakeResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"302", b"Found")
        linter.process_headers([(name, value)])
        linter.finish_content(True)
        return linter

    def test_link_one_note_per_link(self) -> None:
        linter = self.response(b"Link", b'<http://[::1>; rel="preload preconnect"')
        names = self.note_names(linter)
        self.assertEqual(names.count("LINK_BAD_TARGET_URI"), 1)
        self.assertNotIn("BAD_SYNTAX", names)

    def test_link_one_note_per_bad_link(self) -> None:
        linter = self.response(
            b"Link", b"<http://[::1>; rel=preload, <http://[::2>; rel=preconnect"
        )
        names = self.note_names(linter)
        self.assertEqual(names.count("LINK_BAD_TARGET_URI"), 2)
        self.assertNotIn("BAD_SYNTAX", names)

    def test_location_no_bad_syntax(self) -> None:
        names = self.note_names(self.response(b"Location", b"http://["))
        self.assertEqual(names.count("LOCATION_BAD_URI"), 1)
        self.assertNotIn("BAD_SYNTAX", names)
        self.assertNotIn("LOCATION_NOT_ABSOLUTE", names)

    def test_referer_no_bad_syntax(self) -> None:
        linter = FakeRequestLinter()
        linter.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"https://[::1")])
        linter.finish_content(True)
        names = self.note_names(linter)
        self.assertEqual(names.count("REFERER_BAD_URI"), 1)
        self.assertNotIn("BAD_SYNTAX", names)


class LocationFullUriTest(unittest.TestCase):
    "LOCATION_NOT_ABSOLUTE's full_uri is what urljoin gave before resolve_url() was used."

    CASES = [
        (b"/a/./b/../c", "http://example.com/a/c"),
        (b"../x/./y", "http://example.com/x/y"),
        (b"//EXAMPLE.com:80/x", "http://EXAMPLE.com:80/x"),
        (b"//Example.COM/%7e/p?", "http://Example.COM/%7e/p"),
        (b"baz;p=1?x=1#f", "http://example.com/foo/baz;p=1?x=1#f"),
        (b"?q", "http://example.com/foo/bar?q"),
    ]

    def test_full_uri(self) -> None:
        for value, expected in self.CASES:
            linter = FakeResponseLinter()
            linter.process_response_topline(b"HTTP/1.1", b"302", b"Found")
            linter.process_headers([(b"Location", value)])
            linter.finish_content(True)
            notes = [n for n in linter.notes if n.__class__.__name__ == "LOCATION_NOT_ABSOLUTE"]
            self.assertEqual(len(notes), 1, value)
            self.assertEqual(notes[0].vars["full_uri"], expected, value)
