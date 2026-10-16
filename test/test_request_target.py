import unittest

from httplint.message import (
    HttpRequestLinter,
    REQUEST_TARGET_FORM,
    REQUEST_TARGET_FRAGMENT,
    URI_BAD_SYNTAX,
)


def lint(method: bytes, target: bytes) -> HttpRequestLinter:
    linter = HttpRequestLinter()
    linter.process_request_topline(method, target, b"HTTP/1.1")
    linter.process_headers([(b"User-Agent", b"test")])
    linter.finish_content(True)
    return linter


def classes(linter: HttpRequestLinter) -> set:
    return {type(n) for n in linter.notes}


TARGET_NOTES = {URI_BAD_SYNTAX, REQUEST_TARGET_FORM, REQUEST_TARGET_FRAGMENT}


class TestRequestTargetForms(unittest.TestCase):
    def assertClean(self, method: bytes, target: bytes) -> HttpRequestLinter:
        linter = lint(method, target)
        self.assertFalse(classes(linter) & TARGET_NOTES, f"{method!r} {target!r}")
        return linter

    def assertNote(self, method: bytes, target: bytes, note: type) -> None:
        self.assertIn(note, classes(lint(method, target)), f"{method!r} {target!r}")

    def test_origin_form(self) -> None:
        for target in [b"/", b"/a/b", b"/a?b=c", b"/a?", b"//x"]:
            self.assertClean(b"GET", target)

    def test_absolute_form(self) -> None:
        linter = self.assertClean(b"GET", b"http://example.com/a?b")
        self.assertEqual(linter.uri, "http://example.com/a?b")
        self.assertEqual(linter.iri, "http://example.com/a?b")

    def test_asterisk_form(self) -> None:
        self.assertClean(b"OPTIONS", b"*")
        self.assertNote(b"GET", b"*", REQUEST_TARGET_FORM)

    def test_authority_form(self) -> None:
        linter = self.assertClean(b"CONNECT", b"example.com:443")
        self.assertEqual(linter.uri, "example.com:443")

    def test_authority_form_idna(self) -> None:
        linter = self.assertClean(b"CONNECT", "bücher.example:443".encode())
        self.assertEqual(linter.uri, "xn--bcher-kva.example:443")

    def test_connect_other_forms(self) -> None:
        self.assertNote(b"CONNECT", b"/", REQUEST_TARGET_FORM)
        self.assertNote(b"CONNECT", b"http://example.com/", REQUEST_TARGET_FORM)
        self.assertNote(b"CONNECT", b"*", REQUEST_TARGET_FORM)

    def test_origin_form_bad(self) -> None:
        self.assertNote(b"GET", b"/a b", URI_BAD_SYNTAX)
        self.assertNote(b"GET", b"foo", URI_BAD_SYNTAX)

    def test_control_characters_flagged_not_stripped(self) -> None:
        for target in [b"/a\tb", b"/a\x01b", b"/a\x7fb", b"/a\nb", b"/a\rb", b" /a", b"/a "]:
            linter = lint(b"GET", target)
            self.assertIn(URI_BAD_SYNTAX, classes(linter), repr(target))
            self.assertEqual(linter.uri, target.decode(), repr(target))

    def test_absolute_form_control_characters(self) -> None:
        linter = lint(b"GET", b"http://e.com/a\tb")
        self.assertIn(URI_BAD_SYNTAX, classes(linter))
        self.assertEqual(linter.uri, "http://e.com/a\tb")

    def test_fragment_noted_and_chopped(self) -> None:
        for target in [b"/a#b", b"http://example.com/a#b"]:
            linter = lint(b"GET", target)
            self.assertIn(REQUEST_TARGET_FRAGMENT, classes(linter))
            self.assertNotIn(URI_BAD_SYNTAX, classes(linter))
            self.assertNotIn("#", linter.uri or "")
            self.assertIn("#", linter.iri or "")

    def test_authority_to_ascii(self) -> None:
        from httplint.util import authority_to_ascii

        self.assertEqual(
            authority_to_ascii("user:pw@bücher.example:8080"), "user:pw@xn--bcher-kva.example:8080"
        )
        self.assertEqual(authority_to_ascii("[::1]:80"), "[::1]:80")

    # Depends on rfc3986.py's userinfo production, which is being fixed separately.
    @unittest.expectedFailure
    def test_idna_after_userinfo(self) -> None:
        linter = self.assertClean(b"GET", "http://user:pw@bücher.example/".encode())
        self.assertEqual(linter.uri, "http://user:pw@xn--bcher-kva.example/")

    def test_idna_with_port(self) -> None:
        linter = self.assertClean(b"GET", "http://bücher.example:8080/".encode())
        self.assertEqual(linter.uri, "http://xn--bcher-kva.example:8080/")

    def test_non_ascii_path_encoded(self) -> None:
        linter = self.assertClean(b"GET", "/café".encode())
        self.assertEqual(linter.uri, "/caf%C3%A9")
        self.assertEqual(linter.iri, "/café")

    def test_too_long(self) -> None:
        from httplint.message import URI_TOO_LONG

        self.assertNote(b"GET", b"/" + b"a" * 9000, URI_TOO_LONG)

    # Depends on rfc3986.py's userinfo and IPv6 handling, which is being fixed separately.
    @unittest.expectedFailure
    def test_authority_form_userinfo(self) -> None:
        self.assertClean(b"CONNECT", b"user@example.com:443")

    @unittest.expectedFailure
    def test_authority_form_ipv6(self) -> None:
        self.assertClean(b"CONNECT", b"[::1]:443")
