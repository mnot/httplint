import importlib
import re
import sys
import time
import unittest
from functools import partial
from typing import Any, Callable, List, Tuple, Type

from httplint import HttpRequestLinter, HttpResponseLinter, syntax
from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED, HttpField
from httplint.field.broken_field import BrokenField
from httplint.field.list_field import HttpListField
from httplint.field.parsers.link import LINK_BAD_TARGET_URI
from httplint.field.parsers.location import LOCATION_BAD_URI, LOCATION_NOT_ABSOLUTE
from httplint.field.parsers.referer import REFERER_BAD_URI
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FakeResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110, rfc9112
from httplint.types import AddNoteMethodType, ResponseLinterProtocol
from httplint.util import invalid_char_problem


def check_regex() -> None:
    """Grab all the regex in this module."""
    modules = 0
    count = 0
    errors = 0
    for module_name in syntax.__all__:
        modules += 1
        full_name = f"httplint.syntax.{module_name}"
        importlib.import_module(full_name)
        module = sys.modules[full_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, str):
                count += 1
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error as why:
                    errors += 1
                    print("*", module_name, attr_name, why)
    return count, modules, errors


TIME_LIMIT = 1.0  # seconds; the unfixed grammars take many seconds on these inputs
SEMIS = "; " * 24  # the parameters grammar doubled its work for each ";"


def lint_request(name: bytes, value: bytes) -> None:
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
    linter.process_headers([(name, value)])
    linter.finish_content(True)


def lint_response(name: bytes, value: bytes) -> None:
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(name, value)])
    linter.finish_content(True)


def lint_target(target: bytes) -> None:
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", target, b"HTTP/1.1")
    linter.finish_content(True)


class SyntaxBacktrackingTest(unittest.TestCase):
    """Pathological non-matching inputs must fail in bounded time."""

    def check(self, label: str, func: Callable[..., None], *args: bytes) -> None:
        with self.subTest(label):
            start = time.monotonic()
            func(*args)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{label}: {elapsed:.2f}s")

    def test_parameters(self) -> None:
        bad = SEMIS.encode() + b"\x80"
        cases: List[Tuple[str, bool, bytes, bytes]] = [
            ("Content-Type", False, b"Content-Type", b"text/plain" + bad),
            ("Content-Type response", True, b"Content-Type", b"text/plain" + bad),
            ("Accept", False, b"Accept", b"text/plain" + bad),
            ("Accept-Post", True, b"Accept-Post", b"text/plain" + bad),
            ("Accept-Patch", True, b"Accept-Patch", b"text/plain" + bad),
            ("Expect", False, b"Expect", b"a=b" + bad),
            ("Server-Timing", True, b"Server-Timing", b"a" + bad),
            (
                "Link type",
                True,
                b"Link",
                b'<http://a/>; type="text/plain' + SEMIS.encode() + b'\x80"',
            ),
        ]
        for label, response, name, value in cases:
            lint = lint_response if response else lint_request
            self.check(label, lint, name, value)

    def test_range(self) -> None:
        value = b"bytes=" + b",".join([b"0-1"] * 24) + b",\x7f"
        self.check("Range", lint_request, b"Range", value)

    def test_partial_uri(self) -> None:
        value = b"a" * 15000 + b"<"
        self.check("Content-Location", lint_response, b"Content-Location", value)
        self.check("Referer", lint_request, b"Referer", value)

    def test_origin_form(self) -> None:
        self.check("request target", lint_target, b"/" + b"a" * 15000 + b"%zz")


def matches(rule: str, value: str) -> bool:
    return re.match(rf"^\s*(?:{rule})\s*$", value, re.VERBOSE | re.IGNORECASE) is not None


class SyntaxAcceptRejectTest(unittest.TestCase):
    """The backtracking rewrites must accept and reject what they did before."""

    def check(self, rule: str, accepted: List[str], rejected: List[str]) -> None:
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(matches(rule, value))
        for value in rejected:
            with self.subTest(value=value):
                self.assertFalse(matches(rule, value))

    def test_parameters(self) -> None:
        self.check(
            rfc9110.media_type,
            [
                "text/plain",
                "text/plain;",
                "text/plain; ;",
                "text/plain; ; a=b",
                "text/plain;a=b",
                "text/plain ; a=b ;c=d",
                'text/plain; a="x\\"y"',
                'text/plain; a="b;c"; ; d=e',
                "text/plain \t;\t",
            ],
            [
                "text/plain; a",
                "text/plain; a=",
                "text/plain; =b",
                "text/plain a=b",
                'text/plain; a="x',
                'text/plain; a="x\\"',
                "text/plain; a=b c=d",
                "text/plain; ; \x80",
            ],
        )
        self.check(
            rfc9110.expectation,
            ["100-continue", "a=b; ;c=d", 'a="b"; c="d\\"e"'],
            ["a=b; c", 'a="b', "a=b ; ; c="],
        )

    def test_range(self) -> None:
        self.check(
            rfc9110.Range,
            ["bytes=0-1", "bytes=0-", "bytes=-1", "bytes=0-1,-1", "bytes=0-1, 2-3", "bytes=a"],
            ["bytes=", "bytes=0-1,", "bytes=0 -1", "bytes=0-1,\x7f", "0-1"],
        )

    def test_origin_form(self) -> None:
        self.check(
            rfc9112.origin_form,
            ["/", "/a/b", "//x", "/a?", "/a?b=c", "/a?b/c?d", "/a??"],
            ["a", "?a", "/a b", "/a#b", "/a?b c", "/%zz", "/a?%zz"],
        )

    def test_partial_uri(self) -> None:
        self.check(
            rfc9110.partial_URI,
            ["", "a", "/a", "a/b:c", "./a:b", "/a?b=c", "a?b:c", "//host/p?q"],
            ["1:2", "a:b", "//a:a b", "a b"],
        )


class FieldSyntaxCheckTest(unittest.TestCase):
    """HttpField._check_syntax is shared by list, singleton and broken fields."""

    class SingletonF(SingletonField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = "a+"

    class BrokenF(BrokenField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = "a+"

    class ListF(HttpListField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = rfc9110.list_rule("a+")

    def lint(self, field_class: Type[HttpField[Any]], *values: str) -> List[Note]:
        message = FakeResponseLinter()
        field = field_class("X-Test", message)
        for offset, value in enumerate(values):
            field.handle_input(value, partial(message.notes.add, "x"), offset)
        field.finish(partial(message.notes.add, "x", field_name="X-Test"))
        return list(message.notes)

    def classes(self, notes: List[Note]) -> List[type]:
        return [n.__class__ for n in notes]

    def test_detailed_note_for_every_kind(self) -> None:
        "A value that matches in part gets the position and context, not just BAD_SYNTAX."
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                notes = self.lint(field_class, "aab")
                self.assertEqual(self.classes(notes), [BAD_SYNTAX_DETAILED])
                self.assertIn("position 3", notes[0].vars["problem"])

    def test_generic_note_when_nothing_matches(self) -> None:
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                self.assertEqual(self.classes(self.lint(field_class, "b")), [BAD_SYNTAX])

    def test_conforming_value(self) -> None:
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                self.assertEqual(self.classes(self.lint(field_class, " aaa ")), [])

    def test_note_vars(self) -> None:
        "A character that can't be quoted is named by code point."
        notes = self.lint(self.SingletonF, "a`")
        self.assertIn("U+0060", notes[0].vars["problem"])
        self.assertNotIn("`", notes[0].vars["problem"])

    def test_category(self) -> None:
        "Both notes take the field's category, for every kind of field."
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            categorised = type("Categorised", (base,), {"category": categories.CACHING})
            for value in ("aab", "b"):
                with self.subTest(base.__bases__[0].__name__, value=value):
                    notes = self.lint(categorised, value)
                    self.assertEqual(notes[0].category, categories.CACHING)

    def test_levels(self) -> None:
        "A partial match is BAD (detailed note), no match is WARN (generic note)."
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                self.assertEqual(self.lint(base, "aab")[0].level, levels.BAD)
                self.assertEqual(self.lint(base, "b")[0].level, levels.WARN)

    def test_hook_when_parse_raises(self) -> None:
        "The check still runs when parse() raises ValueError, unless it suppressed it first."

        def raises(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            raise ValueError

        def suppresses_then_raises(
            self: HttpField[Any], field_value: str, add_note: AddNoteMethodType
        ) -> str:
            self.suppress_syntax_note()  # type: ignore[attr-defined]
            raise ValueError

        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                plain = type("Raises", (base,), {"parse": raises})
                quiet = type("Quiet", (base,), {"parse": suppresses_then_raises})
                self.assertEqual(self.classes(self.lint(plain, "b")), [BAD_SYNTAX])
                self.assertEqual(self.lint(quiet, "b"), [])

    def test_report_syntax_false(self) -> None:
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                quiet = type("Quiet", (base,), {"report_syntax": False})
                self.assertEqual(self.lint(quiet, "aab"), [])
                self.assertEqual(self.lint(quiet, "b"), [])

    def test_suppress_hook(self) -> None:
        "parse() can suppress the note for its own value, and only for that value."

        def parse(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            if field_value.startswith("b"):
                self.suppress_syntax_note()  # type: ignore[attr-defined]
            return field_value

        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                hooked = type("Hooked", (base,), {"parse": parse})
                self.assertEqual(self.lint(hooked, "b"), [])

    def test_suppress_hook_does_not_leak(self) -> None:
        def parse(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            if field_value.startswith("b"):
                self.suppress_syntax_note()  # type: ignore[attr-defined]
            return field_value

        for base in (self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                hooked = type("Hooked", (base,), {"parse": parse})
                values = ("b", "c") if base is self.BrokenF else ("b, c",)
                self.assertEqual(self.classes(self.lint(hooked, *values)), [BAD_SYNTAX])

    def test_patterns_compiled_once_per_class(self) -> None:
        first = self.SingletonF._syntax_patterns()  # pylint: disable=protected-access
        self.assertIs(first, self.SingletonF._syntax_patterns())  # pylint: disable=protected-access
        child = type("Child", (self.SingletonF,), {"syntax": "b+"})
        self.assertIsNot(first, child._syntax_patterns())  # pylint: disable=protected-access
        self.assertIs(first, self.SingletonF._syntax_patterns())  # pylint: disable=protected-access

    def test_no_syntax(self) -> None:
        none = type("NoSyntax", (self.SingletonF,), {"syntax": False})
        self.assertIsNone(none._syntax_patterns())  # pylint: disable=protected-access
        self.assertEqual(self.lint(none, "anything"), [])


class FieldSyntaxNoteTest(unittest.TestCase):
    """Real fields: one note per defect, and the detailed note for singletons."""

    def notes(self, name: bytes, value: bytes, response: bool = True) -> List[type]:
        linter = HttpResponseLinter() if response else HttpRequestLinter()
        if response:
            linter.process_response_topline(b"HTTP/1.1", b"302", b"Found")
        else:
            linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(name, value)])
        linter.finish_content(True)
        return [n.__class__ for n in linter.notes]

    def test_singleton_detailed(self) -> None:
        self.assertIn(BAD_SYNTAX_DETAILED, self.notes(b"Location", b"http://example.com/a b"))
        self.assertIn(
            BAD_SYNTAX_DETAILED, self.notes(b"Referer", b"http://example.com/a b", response=False)
        )

    def test_hook_users_give_one_note(self) -> None:
        "Location, Referer and Link report an unresolvable URI once, without BAD_SYNTAX."
        for name, value, response, specific in [
            (b"Location", b"http://[", True, LOCATION_BAD_URI),
            (b"Referer", b"https://[::1", False, REFERER_BAD_URI),
            (b"Link", b"<http://[::1>; rel=preload", True, LINK_BAD_TARGET_URI),
        ]:
            with self.subTest(name=name):
                found = self.notes(name, value, response)
                self.assertEqual(found.count(specific), 1, found)
                self.assertFalse(any(issubclass(n, BAD_SYNTAX) for n in found), found)

    def test_order(self) -> None:
        "The note parse() adds comes before the syntax note for the same value."
        found = [
            n
            for n in self.notes(b"Location", b"http://example.com/a b")
            if n in (LOCATION_NOT_ABSOLUTE, BAD_SYNTAX_DETAILED)
        ]
        self.assertEqual(found, [LOCATION_NOT_ABSOLUTE, BAD_SYNTAX_DETAILED])

    def test_hook_suppresses_whole_value(self) -> None:
        "Pins the per-value scope: the stray '>' in this Link isn't reported separately."
        found = self.notes(b"Link", b"<http://[::1>>; rel=dns-prefetch")
        self.assertIn(LINK_BAD_TARGET_URI, found)
        self.assertFalse(any(issubclass(n, BAD_SYNTAX) for n in found), found)

    def problems(self, name: bytes, value: bytes, response: bool = True) -> List[str]:
        linter = HttpResponseLinter() if response else HttpRequestLinter()
        if response:
            linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        else:
            linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(name, value)])
        linter.finish_content(True)
        return [
            str(n.vars["problem"]) for n in linter.notes if issubclass(n.__class__, BAD_SYNTAX_DETAILED)
        ]

    def test_unquotable_character_is_named(self) -> None:
        for name, value, response, expected in [
            (b"Accept-Language", b"a`b", False, "U+0060"),
            (b"Cache-Control", b"a\x00b", True, "U+0000"),
            (b"Allow", b"a\x00b", True, "U+0000"),
            (b"Connection", b"a\x00b", True, "U+0000"),
            (b"WWW-Authenticate", b"Basic `", True, "U+0060"),
        ]:
            with self.subTest(name=name, value=value):
                problems = self.problems(name, value, response)
                self.assertTrue(problems)
                for problem in problems:
                    self.assertIn(expected, problem)
                    self.assertNotIn("''", problem)

    def test_link_hook_is_per_element(self) -> None:
        found = self.notes(b"Link", b"<http://[::1>; rel=preload, </a b>")
        self.assertEqual(sum(1 for n in found if n is BAD_SYNTAX), 1, found)


class InvalidCharProblemTest(unittest.TestCase):
    def test_quoted(self) -> None:
        self.assertEqual(
            invalid_char_problem("ab c", 2), "The invalid character ' ' was found at position 3."
        )
        self.assertEqual(
            invalid_char_problem("a\x80", 1), "The invalid character '\x80' was found at position 2."
        )

    def test_named(self) -> None:
        for char, name in [("`", "U+0060"), ("\x00", "U+0000"), ("\n", "U+000A"), ("\u2028", "U+2028")]:
            with self.subTest(name):
                problem = invalid_char_problem(f"a{char}b", 1)
                self.assertEqual(problem, f"The invalid character {name} was found at position 2.")

    def test_end_of_value(self) -> None:
        self.assertEqual(
            invalid_char_problem("ab", 2), "The value ended unexpectedly at position 3."
        )


def run_regex_check() -> None:
    print("Checking Syntax...")
    count, modules, errors = check_regex()
    print(f"Checked {count} syntax regex in {modules} modules; {errors} errors.")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_regex_check()
    unittest.main()
