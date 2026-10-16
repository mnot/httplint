import unittest

from httplint.note import levels
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

    def test_authority_to_ascii_userinfo(self) -> None:
        from httplint.util import authority_to_ascii

        # Non-ASCII userinfo is percent-encoded, not IDNA-encoded into the host.
        self.assertEqual(authority_to_ascii("bücher@example.com"), "b%C3%BCcher@example.com")
        self.assertEqual(authority_to_ascii("é@example.com"), "%C3%A9@example.com")
        self.assertEqual(
            authority_to_ascii("user:pässword@bücher.example:8080"),
            "user:p%C3%A4ssword@xn--bcher-kva.example:8080",
        )
        self.assertEqual(authority_to_ascii("ü@[::1]:80"), "%C3%BC@[::1]:80")
        # Colons in the password, and more than one "@": userinfo ends at the last one.
        self.assertEqual(authority_to_ascii("u:p:ü@example.com"), "u:p:%C3%BC@example.com")
        self.assertEqual(
            authority_to_ascii("ü@ü@bücher.com"), "%C3%BC@%C3%BC@xn--bcher-kva.com"
        )
        # Existing escapes and ASCII are left alone.
        self.assertEqual(authority_to_ascii("a%40b:c@example.com"), "a%40b:c@example.com")

    def test_iri_to_uri_userinfo(self) -> None:
        from urllib.parse import urlsplit

        from httplint.util import iri_to_uri

        for iri, user, host in [
            ("https://bücher@example.com/x.js", "b%C3%BCcher", "example.com"),
            ("https://u@bücher.example/x.js", "u", "xn--bcher-kva.example"),
            ("https://user:pässword@example.com/x.js", "user", "example.com"),
            ("https://ü@ü@bücher.com/x.js", "%C3%BC@%C3%BC", "xn--bcher-kva.com"),
        ]:
            parts = urlsplit(iri_to_uri(iri))
            self.assertEqual(parts.username, user)
            self.assertEqual(parts.hostname, host)
            self.assertTrue(iri_to_uri(iri).isascii())

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

    def test_authority_form_invalid(self) -> None:
        for target in [
            b"",
            b":443",
            b"example.com:",
            b"example.com",
            b"example.com:99999",
            b"example.com:44a",
            b"user@example.com:443",
            "ü@example.com:443".encode(),
            b"a..b:443",
        ]:
            self.assertNote(b"CONNECT", target, REQUEST_TARGET_FORM)
            self.assertNotIn(URI_BAD_SYNTAX, classes(lint(b"CONNECT", target)), repr(target))

    def test_fragment_consistent_on_failure_paths(self) -> None:
        for target in [b"/a\tb#frag", b"http://a..b/#frag", b"/a#frag"]:
            linter = lint(b"GET", target)
            self.assertIn(REQUEST_TARGET_FRAGMENT, classes(linter), repr(target))
            self.assertNotIn("#", linter.uri or "", repr(target))

    def test_fragment_is_a_warning(self) -> None:
        self.assertEqual(REQUEST_TARGET_FRAGMENT.level, levels.WARN)
        notes = [n for n in lint(b"GET", b"/a#b").notes if isinstance(n, REQUEST_TARGET_FRAGMENT)]
        self.assertEqual(notes[0].level, levels.WARN)

    def test_form_summary_grammar(self) -> None:
        notes = [n for n in lint(b"OPTIONS", b"/").notes if isinstance(n, REQUEST_TARGET_FORM)]
        self.assertFalse(notes)
        notes = [n for n in lint(b"CONNECT", b"/").notes if isinstance(n, REQUEST_TARGET_FORM)]
        self.assertEqual(str(notes[0].summary), "The request target isn't valid for CONNECT requests.")

    def test_authority_form_ipv6(self) -> None:
        self.assertClean(b"CONNECT", b"[::1]:443")
