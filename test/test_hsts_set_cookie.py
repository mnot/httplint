import html
import itertools
import re
import time
import unittest
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type

from httplint import HttpResponseLinter
from httplint.field.deferred_notes import DeferredNotes
from httplint.field.parsers.set_cookie import (
    DAY_OF_MONTH_TOKEN,
    TIME_TOKEN,
    YEAR_TOKEN,
    loose_date_parse,
)
from httplint.field.parsers.strict_transport_security import (
    HSTS_BAD_MAX_AGE,
    HSTS_DUPLICATE_DIRECTIVE,
    HSTS_INVALID,
    HSTS_NO_MAX_AGE,
    HSTS_OVER_HTTP,
    HSTS_VALID,
    strict_transport_security,
)
from httplint.field.utils import RE_FLAGS
from httplint.note import Note
from httplint.syntax import rfc9110

TIME_LIMIT = 1.0  # seconds; these take milliseconds


class FakeNote(Note):
    _summary = "fake"
    _text = "fake"


class OtherNote(Note):
    _summary = "other"
    _text = "other"


class DeferredNotesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.added: List[Tuple[str, Type[Note], Dict[str, Any]]] = []

    def adder(self, label: str) -> Callable[..., Any]:
        def add_note(note: Type[Note], **vrs: Any) -> None:
            self.added.append((label, note, vrs))

        return add_note

    def test_emit_in_order(self) -> None:
        deferred = DeferredNotes()
        deferred.defer(FakeNote, a=1)
        deferred.defer(OtherNote)
        self.assertEqual(self.added, [])
        deferred.emit(self.adder("emit"))
        self.assertEqual(self.added, [("emit", FakeNote, {"a": 1}), ("emit", OtherNote, {})])

    def test_via_uses_its_own_add_note(self) -> None:
        deferred = DeferredNotes()
        deferred.via(self.adder("one"))(FakeNote, x="y")
        deferred.defer(OtherNote)
        deferred.emit(self.adder("emit"))
        self.assertEqual(self.added, [("one", FakeNote, {"x": "y"}), ("emit", OtherNote, {})])

    def test_category_passed_only_when_given(self) -> None:
        deferred = DeferredNotes()
        deferred.defer(FakeNote)
        deferred.defer(OtherNote, category="c")
        deferred.emit(self.adder("emit"))
        self.assertEqual(
            self.added, [("emit", FakeNote, {}), ("emit", OtherNote, {"category": "c"})]
        )

    def test_membership(self) -> None:
        deferred = DeferredNotes()
        self.assertFalse(deferred.has(FakeNote))
        deferred.defer(FakeNote)
        self.assertTrue(deferred.has(FakeNote))
        self.assertTrue(deferred.has(OtherNote, FakeNote))
        self.assertFalse(deferred.has(OtherNote))
        deferred.via(self.adder("x"))(OtherNote)
        self.assertTrue(deferred.has(OtherNote))

    def test_emit_without_target(self) -> None:
        deferred = DeferredNotes()
        deferred.defer(FakeNote)
        with self.assertRaises(ValueError):
            deferred.emit()

    def test_emit_twice_repeats(self) -> None:
        deferred = DeferredNotes()
        deferred.defer(FakeNote)
        deferred.emit(self.adder("a"))
        deferred.emit(self.adder("b"))
        self.assertEqual([a[0] for a in self.added], ["a", "b"])


def lint_hsts(value: bytes, base_uri: str = "https://example.com/", status: bytes = b"200") -> Any:
    linter = HttpResponseLinter()
    linter.base_uri = base_uri
    linter.process_response_topline(b"HTTP/1.1", status, b"OK")
    linter.process_headers([(b"Strict-Transport-Security", value)])
    linter.finish_content(True)
    return linter


def all_notes(notes: Iterable[Note]) -> List[Note]:
    found: List[Note] = []
    for note in notes:
        found.append(note)
        found.extend(all_notes(note.subnotes))
    return found


# --- Strict-Transport-Security -------------------------------------------------------------------

OLD_STS_DIR = (
    rf"(?: {rfc9110.token} (?: {rfc9110.BWS} = {rfc9110.BWS} {rfc9110.parameter_value} )? )"
)
OLD_STS_SYNTAX = (
    rf"(?: {OLD_STS_DIR} (?: {rfc9110.OWS} ; {rfc9110.OWS} {OLD_STS_DIR} )* (?: {rfc9110.OWS} ;)? )"
)


def sts_matches(rule: str, value: str) -> bool:
    return re.match(rf"^\s*(?:{rule})\s*$", value, RE_FLAGS) is not None


class HSTSSyntaxTest(unittest.TestCase):
    def test_differential(self) -> None:
        "The grammar now also allows empty directives, and nothing else changes."
        simple_dir = re.compile(r"[a-z-]+(?:\s*=\s*[a-z-]+)?")

        def reference(value: str) -> bool:
            "RFC 6797 Section 6.1, for strings without quotes; but not a blank string."
            return value.strip() != "" and all(
                s == "" or simple_dir.fullmatch(s) for s in (p.strip() for p in value.split(";"))
            )

        checked = 0
        for length in range(0, 8):
            for chars in itertools.product("a=; -", repeat=length):
                value = "".join(chars)
                old = sts_matches(OLD_STS_SYNTAX, value)
                new = sts_matches(strict_transport_security.syntax, value)
                segments = [p.strip() for p in value.split(";")]
                has_empty = "" in segments[:-1] or value.strip() == ""
                with self.subTest(value=value):
                    if old:
                        self.assertTrue(new)
                    if new and not old:
                        self.assertTrue(has_empty)
                    self.assertEqual(new, reference(value))
                checked += 1
        self.assertGreater(checked, 50000)

    def test_quoted(self) -> None:
        accepted = [
            'max-age="31536000"',
            'max-age = "100" ; includeSubDomains',
            'max-age="a;b"',
            'max-age=100; foo="x\\"y"',
            "max-age=100;;; includeSubDomains",
            "; max-age=100",
            "max-age=100 ;",
            ";",
            " ; ; ",
        ]
        rejected = [
            "",
            "   ",
            'max-age="100',
            "=100",
            "max-age=",
            "max-age=100 includeSubDomains",
            "max-age=100;\x80",
            'foo="x\\"',
        ]
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(sts_matches(strict_transport_security.syntax, value))
        for value in rejected:
            with self.subTest(value=value):
                self.assertFalse(sts_matches(strict_transport_security.syntax, value))

    def test_timing(self) -> None:
        "Regression: a failed match must be linear (an all-optional grammar is not)."
        cases = {
            "leading whitespace": " " * 20000 + "\x80",
            "trailing whitespace": "max-age=1" + " " * 20000 + "\x80",
            "whitespace between semicolons": ";" + " " * 5000 + ";" + " " * 5000 + "\x80",
            "semicolons": "; " * 10000 + "\x80",
            "spaced semicolons": "max-age=1" + " ; " * 5000 + "\x80",
            "directives": " ; ".join(["a = b"] * 3000) + " \x80",
        }
        for label, value in cases.items():
            with self.subTest(label):
                start = time.monotonic()
                self.assertFalse(sts_matches(strict_transport_security.syntax, value))
                elapsed = time.monotonic() - start
                self.assertLess(elapsed, TIME_LIMIT, f"{label}: {elapsed:.2f}s")

    def test_timing_linter(self) -> None:
        start = time.monotonic()
        lint_hsts(b"max-age=1" + b" " * 20000 + b"\x80")
        lint_hsts(b";" + b" " * 5000 + b";" + b" " * 5000 + b"\x80")
        self.assertLess(time.monotonic() - start, TIME_LIMIT)


class HSTSBehaviourTest(unittest.TestCase):
    def test_redirect_over_http(self) -> None:
        "RFC 6797 Section 8.1 has no 301 exemption."
        for status in [b"200", b"301", b"302", b"404"]:
            with self.subTest(status=status):
                classes = {
                    type(n)
                    for n in all_notes(
                        lint_hsts(b"max-age=31536000", "http://example.com/", status).notes
                    )
                }
                self.assertIn(HSTS_OVER_HTTP, classes)
                self.assertIn(HSTS_INVALID, classes)
                self.assertNotIn(HSTS_VALID, classes)

    def test_over_https(self) -> None:
        classes = {type(n) for n in all_notes(lint_hsts(b"max-age=31536000").notes)}
        self.assertIn(HSTS_VALID, classes)
        self.assertNotIn(HSTS_OVER_HTTP, classes)

    def test_empty_directives_not_duplicates(self) -> None:
        classes = {type(n) for n in all_notes(lint_hsts(b"max-age=100;;; includeSubDomains").notes)}
        self.assertNotIn(HSTS_DUPLICATE_DIRECTIVE, classes)
        self.assertIn(HSTS_VALID, classes)

    def test_bad_max_age_detail(self) -> None:
        "The offending value is shown in a code span, but never as an empty one."
        for raw, shown in [
            (b"max-age=-5", "[-5]"),
            (b'max-age="-5"', '["-5"]'),
            (b"max-age=foo", "[foo]"),
            (b'max-age=""', '[""]'),
            (b"max-age=", "(empty)"),
            (b"max-age", "(empty)"),
            (b"max-age=` `", "(empty)"),
            (b"max-age=``", "(empty)"),
        ]:
            with self.subTest(raw=raw):
                found = [
                    n for n in all_notes(lint_hsts(raw).notes) if isinstance(n, HSTS_BAD_MAX_AGE)
                ]
                self.assertEqual(len(found), 1)
                note = found[0]
                note.vars.update({"field_name": "Strict-Transport-Security"})
                detail = (
                    html.unescape(str(note.detail)).replace("<code>", "[").replace("</code>", "]")
                )
                self.assertIn(shown, detail)
                self.assertNotIn("[]", detail)

    def test_bad_max_age_backticks(self) -> None:
        found = [
            n for n in all_notes(lint_hsts(b"max-age=a`b").notes) if isinstance(n, HSTS_BAD_MAX_AGE)
        ]
        self.assertEqual(len(found), 1)
        found[0].vars.update({"field_name": "Strict-Transport-Security"})
        self.assertIn("<code>ab</code>", str(found[0].detail))

    def test_max_age_digit_bound(self) -> None:
        "Like Age, any size up to 4000 digits is a valid integer; RFC 6797 has no upper bound."
        for digits, valid in [(21, True), (4000, True), (4001, False)]:
            with self.subTest(digits=digits):
                classes = {type(n) for n in all_notes(lint_hsts(b"max-age=" + b"9" * digits).notes)}
                self.assertEqual(HSTS_BAD_MAX_AGE in classes, not valid)
                self.assertEqual(HSTS_VALID in classes, valid)

    def test_quoted_semicolons(self) -> None:
        "A ';' inside a quoted-string doesn't separate directives."
        for raw in [
            b'foo="a;b"; bar="a;b"; max-age=100',
            b'foo="a;max-age=1"; max-age=100',
            b'foo="a\\";b"; bar="\\\\"; max-age=100',
        ]:
            with self.subTest(raw=raw):
                linter = lint_hsts(raw)
                classes = {type(n) for n in all_notes(linter.notes)}
                self.assertNotIn(HSTS_DUPLICATE_DIRECTIVE, classes)
                self.assertIn(HSTS_VALID, classes)
                self.assertEqual(linter.headers.parsed["strict-transport-security"]["max-age"], 100)

    def test_quoted_max_age_with_semicolon(self) -> None:
        classes = {type(n) for n in all_notes(lint_hsts(b'max-age="1;2"').notes)}
        self.assertIn(HSTS_BAD_MAX_AGE, classes)
        self.assertNotIn(HSTS_NO_MAX_AGE, classes)


# --- Set-Cookie ----------------------------------------------------------------------------------

OLD_TIME = r"^(\d{2}:\d{2}:\d{2})(?:\D)?"
OLD_DAY = r"^(\d\d?)(?:\D)?"
OLD_YEAR = r"^(\d{2,4})(?:\D)?"


def tokens(alphabet: str, max_length: int) -> Iterable[str]:
    for length in range(1, max_length + 1):
        for chars in itertools.product(alphabet, repeat=length):
            yield "".join(chars)


def leading_digits(token: str) -> int:
    return len(token) - len(token.lstrip("0123456789"))


class CookieDateRegexTest(unittest.TestCase):
    def test_day_of_month(self) -> None:
        "Only a longer digit run than 1*2DIGIT is newly rejected."
        for token in tokens("019a:", 6):
            old = re.match(OLD_DAY, token)
            new = re.match(DAY_OF_MONTH_TOKEN, token)
            with self.subTest(token=token):
                self.assertEqual(new is not None, leading_digits(token) in (1, 2))
                if new:
                    self.assertIsNotNone(old)
                    assert old
                    self.assertEqual(old.group(1), new.group(1))
                if old and not new:
                    self.assertGreater(leading_digits(token), 2)

    def test_year(self) -> None:
        for token in tokens("019a:", 7):
            old = re.match(OLD_YEAR, token)
            new = re.match(YEAR_TOKEN, token)
            with self.subTest(token=token):
                self.assertEqual(new is not None, leading_digits(token) in (2, 3, 4))
                if new:
                    self.assertIsNotNone(old)
                    assert old
                    self.assertEqual(old.group(1), new.group(1))
                if old and not new:
                    self.assertGreater(leading_digits(token), 4)

    def test_time(self) -> None:
        "Fields may be one digit; the last field may not run on into more digits."
        reference = re.compile(r"\d{1,2}:\d{1,2}:\d{1,2}(?:\D.*)?", re.DOTALL)
        for token in tokens("019:a", 8):
            old = re.match(OLD_TIME, token)
            new = re.match(TIME_TOKEN, token)
            with self.subTest(token=token):
                self.assertEqual(new is not None, reference.fullmatch(token) is not None)
                if old and not new:
                    self.assertRegex(token, r"^\d\d:\d\d:\d\d\d")
                if new and not old:
                    self.assertNotRegex(token, r"^\d\d:\d\d:\d\d")
                if new and old:
                    self.assertEqual(old.group(1), new.group(1))

    def test_loose_date_parse(self) -> None:
        self.assertEqual(loose_date_parse("Wed, 09 Jun 2021 10:18:14 GMT"), 1623233894)
        self.assertEqual(loose_date_parse("Wed, 9 Jun 2021 1:18:14 GMT"), 1623201494)
        self.assertEqual(loose_date_parse("Wed, 09 Jun 2021 1:2:3 GMT"), 1623200523)
        for bad in [
            "Wed, 123 Jun 2021 10:18:14 GMT",
            "Wed, 09 Jun 20211 10:18:14 GMT",
            "Wed, 09 Jun 2021 10:18:145 GMT",
        ]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    loose_date_parse(bad)

    def test_timing(self) -> None:
        "Guard: the old regexes were not slow either."
        cases = [
            "Wed, " + "1" * 100000 + " Jun 2021 10:18:14 GMT",
            "Wed, 09 Jun " + "2" * 100000 + " 10:18:14 GMT",
            "Wed, 09 Jun 2021 " + "1:" * 50000 + " GMT",
            " ".join(["1:1:1"] * 20000),
        ]
        for value in cases:
            with self.subTest(value=value[:30]):
                start = time.monotonic()
                try:
                    loose_date_parse(value)
                except ValueError:
                    pass
                self.assertLess(time.monotonic() - start, TIME_LIMIT)


def lint_cookie(value: bytes) -> Tuple[Any, List[Note]]:
    linter = HttpResponseLinter()
    linter.base_uri = "https://example.com/"
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(b"Set-Cookie", value)])
    linter.finish_content(True)
    return linter.headers.parsed.get("set-cookie"), all_notes(linter.notes)


class CookieMaxAgeTest(unittest.TestCase):
    def attrs(self, value: bytes) -> Optional[List[Any]]:
        parsed, _ = lint_cookie(value)
        self.assertEqual(len(parsed), 1)
        return list(parsed[0][2])

    def test_negative(self) -> None:
        self.assertEqual(self.attrs(b"a=b; Max-Age=-1"), [("Max-Age", -1)])

    def test_huge_keeps_cookie(self) -> None:
        for value in [b"9" * 5000, b"\xb2", b"\xd9\xa5"]:
            with self.subTest(value=value):
                self.assertEqual(self.attrs(b"a=b; Max-Age=" + value), [])

    def test_timing(self) -> None:
        "Guard: main handles these in time too (it just drops the cookie)."
        start = time.monotonic()
        lint_cookie(b"a=b; Max-Age=" + b"9" * 100000)
        lint_cookie(b"a=b; Expires=" + b"1" * 100000)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)


if __name__ == "__main__":
    unittest.main()
