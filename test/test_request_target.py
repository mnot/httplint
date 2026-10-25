import time
import unittest

from httplint.message import (
    REQUEST_TARGET_FORM,
    REQUEST_TARGET_FRAGMENT,
    URI_BAD_SYNTAX,
    HttpRequestLinter,
)
from httplint.note import levels


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

    def test_host_to_ascii_keeps_deviation_characters(self) -> None:
        from httplint.util import host_to_ascii

        # Where IDNA2003 and IDNA2008 differ (UTS #46, Table 1): the IDNA2003 result is a
        # different domain.
        for host, ascii_host in [
            ("faß.de", "xn--fa-hia.de"),  # not fass.de
            ("βόλος.com", "xn--nxasmm1c.com"),  # not xn--nxasmq6b.com
            ("ශ්\u200dරී.com", "xn--10cl1a0b660p.com"),  # ZWJ kept
            ("نامه\u200cای.com", "xn--mgba3gch31f060k.com"),  # ZWNJ kept
        ]:
            with self.subTest(host=host):
                self.assertEqual(host_to_ascii(host), ascii_host)
                self.assertNotEqual(host.encode("idna").decode(), ascii_host)

    def test_host_to_ascii_maps_case_and_compatibility_characters(self) -> None:
        from httplint.util import host_to_ascii

        self.assertEqual(host_to_ascii("BÜCHER.Example"), "xn--bcher-kva.example")
        self.assertEqual(host_to_ascii("ｗｗｗ.ü.example"), "www.xn--tda.example")
        self.assertEqual(host_to_ascii("bücher.example."), "xn--bcher-kva.example.")

    def test_host_to_ascii_falls_back_for_what_idna2008_forbids(self) -> None:
        from httplint.util import host_to_ascii

        # Browsers accept these (URL Standard: UTS #46, not IDNA2008); so did we.
        self.assertEqual(host_to_ascii("☕.example"), "xn--53h.example")
        self.assertEqual(host_to_ascii("ü_.example"), "xn--_-dha.example")
        self.assertEqual(host_to_ascii("-ü.example"), "xn----eha.example")

    def test_host_to_ascii_falls_back_a_label_at_a_time(self) -> None:
        from httplint.util import host_to_ascii

        # One label IDNA2008 forbids shouldn't cost the others their right answer.
        for host, ascii_host in [
            ("_dmarc.faß.de", "_dmarc.xn--fa-hia.de"),
            ("_acme-challenge.faß.de", "_acme-challenge.xn--fa-hia.de"),
            ("www_1.faß.de", "www_1.xn--fa-hia.de"),
            ("-b.faß.de", "-b.xn--fa-hia.de"),
            ("_x.βόλος.com", "_x.xn--nxasmm1c.com"),
            ("ab--c.βόλος.com", "ab--c.xn--nxasmm1c.com"),
            ("☕.faß.de", "xn--53h.xn--fa-hia.de"),
        ]:
            with self.subTest(host=host):
                self.assertEqual(host_to_ascii(host), ascii_host)
        # A label that is both forbidden and has a deviation character still gets IDNA2003.
        self.assertEqual(host_to_ascii("x.faß-.de"), "x.fass-.de")

    def test_host_to_ascii_dots_and_labels(self) -> None:
        from httplint.util import host_to_ascii

        self.assertEqual(host_to_ascii("faß。de"), "xn--fa-hia.de")  # ideographic full stop
        self.assertEqual(host_to_ascii("ü."), "xn--tda.")
        self.assertEqual(host_to_ascii("ÜBER.Example.COM"), "xn--ber-goa.example.com")
        with self.assertRaises(UnicodeError):
            host_to_ascii("ü." + "a" * 64)  # an ASCII label that's too long, as before
        # 250 characters: long hosts are fine, as with the codec.
        long_host = ("a" * 60 + ".") * 4 + "faß.de"
        self.assertEqual(host_to_ascii(long_host), ("a" * 60 + ".") * 4 + "xn--fa-hia.de")

    def test_host_to_ascii_is_fast_on_hostile_input(self) -> None:
        import time

        from httplint.util import host_to_ascii

        # idna 3.7-3.13 decode an xn-- label with a quadratic codec; these must never
        # get to it, or to the codec's own NFKC amplification.
        for host in [
            "xn--" + "a" * 1_000_000 + ".ü",
            "ü.xn--" + "a" * 1_000_000,
            "ﷺ" * 65_536,
            "ü" * 1_000_000,
            "ب" + "1\u200c" * 100_000 + "ب",
        ]:
            start = time.monotonic()
            with self.assertRaises(UnicodeError):
                host_to_ascii(host)
            self.assertLess(time.monotonic() - start, 2.0, host[:20])
        # Many short labels are linear too (and valid; there's no total length limit).
        start = time.monotonic()
        host_to_ascii("ü." * 100_000)
        self.assertLess(time.monotonic() - start, 5.0)

    def test_host_to_ascii_leaves_ascii_alone(self) -> None:
        from httplint.util import host_to_ascii

        self.assertEqual(host_to_ascii("EXAMPLE.com"), "EXAMPLE.com")
        self.assertEqual(host_to_ascii("xn--bcher-kva.example"), "xn--bcher-kva.example")
        self.assertEqual(host_to_ascii("a_b.example"), "a_b.example")

    def test_host_to_ascii_rejects_what_neither_accepts(self) -> None:
        from httplint.util import host_to_ascii

        for host in ["a..b", "ü..b", "ü" * 64 + ".com", ".ü"]:
            with self.subTest(host=host):
                with self.assertRaises(UnicodeError):
                    host_to_ascii(host)

    def test_idna2008_host_in_request_target(self) -> None:
        linter = self.assertClean(b"GET", "http://faß.de/straße".encode())
        self.assertEqual(linter.uri, "http://xn--fa-hia.de/stra%C3%9Fe")
        linter = self.assertClean(b"CONNECT", "faß.de:443".encode())
        self.assertEqual(linter.uri, "xn--fa-hia.de:443")

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
        self.assertEqual(authority_to_ascii("ü@ü@bücher.com"), "%C3%BC%40%C3%BC@xn--bcher-kva.com")
        # Existing escapes and ASCII are left alone.
        self.assertEqual(authority_to_ascii("a%40b:c@example.com"), "a%40b:c@example.com")

    def test_authority_to_ascii_unsafe_ascii_userinfo(self) -> None:
        from urllib.parse import urlsplit

        from httplint.util import authority_to_ascii

        # ASCII that userinfo can't carry is percent-encoded too, as in the path.
        for userinfo, encoded in [
            ('u"x', "u%22x"),
            ("u<x>", "u%3Cx%3E"),
            ("u\\x", "u%5Cx"),
            ("u x", "u%20x"),
            ("u[x]", "u%5Bx%5D"),
            ("a@b", "a%40b"),
            ("u/x?y#z", "u%2Fx%3Fy%23z"),
        ]:
            with self.subTest(userinfo=userinfo):
                authority = authority_to_ascii(f"{userinfo}:pw@example.com")
                self.assertEqual(authority, f"{encoded}:pw@example.com")
                parts = urlsplit(f"https://{authority}/")
                self.assertEqual(parts.hostname, "example.com")
                self.assertEqual(parts.password, "pw")
        # What it may carry is left alone, escapes included.
        allowed = "Az09-._~!$&'()*+,;=:%41"
        self.assertEqual(authority_to_ascii(f"{allowed}@example.com"), f"{allowed}@example.com")
        self.assertEqual(authority_to_ascii('"@[::1]'), "%22@[::1]")

    def test_unsafe_userinfo_is_still_flagged(self) -> None:
        # The converted URI is valid, but the target as sent wasn't.
        for target in [
            'http://u"x@example.com/',
            "http://u<@example.com/",
            "http://u\\@example.com/",
            "http://a@b@example.com/",
            "http://u%zz@example.com/",
        ]:
            with self.subTest(target=target):
                self.assertNote(b"GET", target.encode(), URI_BAD_SYNTAX)
                self.assertTrue((lint(b"GET", target.encode()).uri or "").isascii())
        for target in ["http://us\u00e9r:p\u00e4ss@example.com/", "http://u:p%40q@example.com/"]:
            with self.subTest(target=target):
                self.assertClean(b"GET", target.encode())

    def test_encoding_userinfo_doesnt_change_the_length_reported(self) -> None:
        from httplint.message import URI_TOO_LONG
        from httplint.util import f_num

        # 7,920 characters as sent; escaping the 100 quotes would take it past 8,000.
        target = b"http://" + b'"' * 100 + b"@example.com/" + b"a" * 7800
        linter = lint(b"GET", target)
        self.assertNotIn(URI_TOO_LONG, classes(linter))
        self.assertEqual(linter.uri_length, len(target))
        # Over the limit, the length is the one as sent (as it was before userinfo was escaped).
        target = b"http://" + b"a" * 7990 + b'"@example.com/'
        note = next(n for n in lint(b"GET", target).notes if isinstance(n, URI_TOO_LONG))
        self.assertIn(f"({f_num(len(target))} characters)", str(note.summary))
        # Other conversion still counts: the path's escapes are part of the URI.
        linter = lint(b"GET", b"http://example.com/" + b'"' * 10)
        self.assertEqual(linter.uri_length, len(b"http://example.com/" + b"%22" * 10))

    def test_userinfo_escape_growth(self) -> None:
        from httplint.util import userinfo_escape_growth

        self.assertEqual(userinfo_escape_growth('https://u"x:p<w@h/'), 4)
        self.assertEqual(userinfo_escape_growth("https://a@b@h/"), 2)
        self.assertEqual(userinfo_escape_growth("https://us\u00e9r@h/"), 0)  # not ASCII
        self.assertEqual(userinfo_escape_growth("https://u-._~!$&'()*+,;=:%41@h/"), 0)
        self.assertEqual(userinfo_escape_growth('https://h/p@q"r'), 0)  # not userinfo

    def test_referer_matching_the_target_is_the_same_origin(self) -> None:
        from httplint.field.parsers.referer import REFERER_SECURE_TO_DIFFERENT_ORIGIN

        for target in [
            'https://u"x@example.com/p',
            "https://u\\@example.com/p",
            "https://a@b@example.com/p",
            "https://u<@example.com/",
        ]:
            with self.subTest(target=target):
                linter = HttpRequestLinter()
                linter.process_request_topline(b"GET", target.encode(), b"HTTP/1.1")
                linter.process_headers([(b"Referer", target.encode()), (b"User-Agent", b"t")])
                self.assertNotIn(REFERER_SECURE_TO_DIFFERENT_ORIGIN, classes(linter))
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"https://example.com/p", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"https://example.org/p"), (b"User-Agent", b"t")])
        self.assertIn(REFERER_SECURE_TO_DIFFERENT_ORIGIN, classes(linter))

    def test_iri_to_uri_userinfo(self) -> None:
        from urllib.parse import urlsplit

        from httplint.util import iri_to_uri

        for iri, user, host in [
            ("https://bücher@example.com/x.js", "b%C3%BCcher", "example.com"),
            ("https://u@bücher.example/x.js", "u", "xn--bcher-kva.example"),
            ("https://user:pässword@example.com/x.js", "user", "example.com"),
            ("https://ü@ü@bücher.com/x.js", "%C3%BC%40%C3%BC", "xn--bcher-kva.com"),
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
        self.assertEqual(
            str(notes[0].summary), "The request target isn't valid for CONNECT requests."
        )

    def test_authority_form_ipv6(self) -> None:
        self.assertClean(b"CONNECT", b"[::1]:443")

    def test_authority_form_empty_host_or_port(self) -> None:
        "Guard: the grammar allows these, but a CONNECT target needs a host and a port."
        for target in [b":443", b"example.com:", b"[::1]:", b":", b"%41:", b"[::1]:65536"]:
            self.assertEqual(
                classes(lint(b"CONNECT", target)) & TARGET_NOTES,
                {REQUEST_TARGET_FORM},
                repr(target),
            )
        for target in [b"example.com:0", b"example.com:65535", b"example.com:00080", b"a%41:1"]:
            self.assertClean(b"CONNECT", target)
        self.assertEqual(
            classes(lint(b"CONNECT", b"example.com:65536")) & TARGET_NOTES, {REQUEST_TARGET_FORM}
        )

    def test_authority_form_backtracking(self) -> None:
        "Long CONNECT targets that don't match rfc9112.authority_form fail in bounded time."
        n = 15000
        bad = b"^"  # fails the grammar; a control character would be rejected before it
        for label, target in [
            ("host", b"a" * n + b":443" + bad),
            ("pct", b"%41" * n + b":443" + bad),
            ("dots", b"1." * n + b":443" + bad),
            ("port", b"a:" + b"1" * n + bad),
            ("IPv6", b"[" + b"1:" * n + b"]:443" + bad),
            ("no port", b"a" * n),
            ("host colons", b"a:" * n + bad),
        ]:
            with self.subTest(label):
                start = time.monotonic()
                self.assertNote(b"CONNECT", target, REQUEST_TARGET_FORM)
                elapsed = time.monotonic() - start
                self.assertLess(elapsed, 1.0, f"{label}: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
