"""
Fields that report a syntax defect with a specific note give that defect one note; a value with a
second, unrelated syntax defect still gets the generic syntax note.
"""

import unittest
from functools import partial
from typing import Iterable, List, Tuple, Type

from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.broken_field import BrokenField
from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.list_field import HttpListField
from httplint.field.parsers.accept import ACCEPT_BAD_SYNTAX
from httplint.field.parsers.accept_language import ACCEPT_LANGUAGE_BAD_SYNTAX
from httplint.field.parsers.accept_patch import ACCEPT_PATCH_BAD_SYNTAX
from httplint.field.parsers.accept_post import ACCEPT_POST_BAD_SYNTAX
from httplint.field.parsers.access_control_max_age import (
    CORS_MAX_AGE_INVALID,
    CORS_MAX_AGE_NEGATIVE,
)
from httplint.field.parsers.age import AGE_NEGATIVE, AGE_NOT_INT
from httplint.field.parsers.content_range import (
    CONTENT_RANGE_INVALID_ASTERISK,
    CONTENT_RANGE_MISSING_SLASH,
    CONTENT_RANGE_MISSING_UNIT,
    RANGE_INVALID_INTEGER,
)
from httplint.field.parsers.strict_transport_security import HSTS_BAD_MAX_AGE
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FakeRequestLinter, FakeResponseLinter
from httplint.i18n import L_
from httplint.note import Note
from httplint.syntax import rfc9110
from httplint.types import ResponseLinterProtocol

GENERIC = (BAD_SYNTAX, BAD_SYNTAX_DETAILED)


def note_classes(
    linter_class: type, name: str, *values: str, status_code: int = 200
) -> List[Type[Note]]:
    "The classes of the notes the message gets for these field lines, in order."
    message = linter_class()
    if isinstance(message, FakeResponseLinter):
        message.status_code = status_code
    message.headers.process([(name.encode(), value.encode("latin-1")) for value in values])
    message.post_checks()
    handler = message.headers.handlers[name.lower()]
    handler.post_check(
        partial(
            message.notes.add,
            f"field-{name.lower()}",
            field_name=handler.canonical_name,
            field_type=L_("header"),
        )
    )
    classes: List[Type[Note]] = []

    def collect(notes: Iterable[Note]) -> None:
        for note in notes:
            classes.append(type(note))
            collect(note.subnotes)

    collect(message.notes)
    return classes


class AcceptMediaTypeTest(unittest.TestCase):
    "Accept, Accept-Patch and Accept-Post share the media-type handling."

    fields = [
        (FakeRequestLinter, "Accept", ACCEPT_BAD_SYNTAX),
        (FakeResponseLinter, "Accept-Patch", ACCEPT_PATCH_BAD_SYNTAX),
        (FakeResponseLinter, "Accept-Post", ACCEPT_POST_BAD_SYNTAX),
    ]

    def test_malformed_media_type_gets_one_note(self) -> None:
        for linter, name, specific in self.fields:
            for value in ["invalid", "text/html/", "inv alid", "invalid; a=b", "invalid;q=0.5"]:
                with self.subTest(field=name, value=value):
                    self.assertEqual(note_classes(linter, name, value), [specific])

    def test_second_defect_keeps_the_generic_note(self) -> None:
        for linter, name, specific in self.fields:
            for value in [
                "invalid; a",
                "invalid; a=b c",
                "invalid; =b",
                "invalid;baz",
                "invalid;=x",
                "invalid;x=y z",
                'invalid;"',
                "invalid;q=",
                "invalid;q=0.5 x",
                "invalid;a=b;c",
            ]:
                with self.subTest(field=name, value=value):
                    notes = note_classes(linter, name, value)
                    self.assertEqual(notes[0], specific)
                    self.assertEqual(len(notes), 2)
                    self.assertIn(notes[1], (BAD_SYNTAX, BAD_SYNTAX_DETAILED))

    def test_suppression_is_per_list_element(self) -> None:
        for linter, name, specific in self.fields:
            with self.subTest(field=name):
                notes = note_classes(linter, name, "invalid, text/html; a")
                self.assertEqual(notes[0], specific)
                self.assertEqual(len(notes), 2)
                self.assertIn(notes[1], (BAD_SYNTAX, BAD_SYNTAX_DETAILED))

    def test_second_defect_in_one_element_only(self) -> None:
        for linter, name, specific in self.fields:
            with self.subTest(field=name):
                notes = note_classes(linter, name, "invalid;baz, invalid;a=b, invalid;q=")
                self.assertEqual(notes.count(specific), 3)
                self.assertEqual(len([n for n in notes if n in GENERIC]), 2)

    def test_valid_values_get_no_notes(self) -> None:
        for linter, name, _ in self.fields:
            with self.subTest(field=name):
                self.assertEqual(note_classes(linter, name, "text/html; charset=utf-8"), [])


class AcceptLanguageTest(unittest.TestCase):
    def notes(self, *values: str) -> List[Type[Note]]:
        return note_classes(FakeRequestLinter, "Accept-Language", *values)

    def test_extra_parameter_gets_one_note(self) -> None:
        for value in ["en; foo=bar", "en;q=0.5;foo=bar", "en;foo=bar;q=0.5", 'en; foo="a;b"']:
            with self.subTest(value=value):
                self.assertEqual(self.notes(value), [ACCEPT_LANGUAGE_BAD_SYNTAX])

    def test_second_defect_keeps_the_generic_note(self) -> None:
        for value in [
            "en; foo=bar; q=abc",
            "e n; foo=bar",
            "en; foo=bar; q=1; q=0.5",
            ";foo=bar",
            "en;foo=bar;q=",
            "en;foo=bar;q=0.5 x",
            "en;foo=bar;q=1.0000",
            "en;foo=bar;baz",
            "en;foo=bar;=x",
            "en;foo=bar;x=y z",
            "en;foo=bar;;",
            'en;foo=bar;"',
            "en;baz;foo=bar",
        ]:
            with self.subTest(value=value):
                notes = self.notes(value)
                self.assertIn(ACCEPT_LANGUAGE_BAD_SYNTAX, notes)
                self.assertEqual(len([n for n in notes if n in GENERIC]), 1)

    def test_single_bad_q_gets_one_note(self) -> None:
        for value in ["en;q=abc", "en;q=1.0000", "en;q=", "en;q=0.5 x"]:
            with self.subTest(value=value):
                notes = self.notes(value)
                self.assertEqual(len(notes), 1)
                self.assertIn(notes[0], GENERIC)

    def test_second_defect_in_one_element_only(self) -> None:
        notes = self.notes("en;foo=bar;q=, fr;foo=bar, de;q=abc")
        self.assertEqual(notes.count(ACCEPT_LANGUAGE_BAD_SYNTAX), 2)
        self.assertEqual(len([n for n in notes if n in GENERIC]), 2)

    def test_suppression_is_per_list_element(self) -> None:
        notes = self.notes("en; foo=bar, fr; q=abc")
        self.assertEqual(notes[0], ACCEPT_LANGUAGE_BAD_SYNTAX)
        self.assertEqual(len(notes), 2)
        self.assertIn(notes[1], (BAD_SYNTAX, BAD_SYNTAX_DETAILED))


class DeltaSecondsTest(unittest.TestCase):
    "Guards: Age and Access-Control-Max-Age give one note per bad value, as they did with the flag."

    def test_age(self) -> None:
        for value, expected in [
            ("foo", [AGE_NOT_INT]),
            ("1.5", [AGE_NOT_INT]),
            ("1 0", [AGE_NOT_INT]),
            ("-5", [AGE_NEGATIVE]),
            ("5", []),
        ]:
            with self.subTest(value=value):
                self.assertEqual(note_classes(FakeResponseLinter, "Age", value), expected)

    def test_access_control_max_age(self) -> None:
        for value, expected in [
            ("foo", [CORS_MAX_AGE_INVALID]),
            ("1.5", [CORS_MAX_AGE_INVALID]),
            ("-5", [CORS_MAX_AGE_NEGATIVE]),
            ("5", []),
        ]:
            with self.subTest(value=value):
                notes = note_classes(FakeResponseLinter, "Access-Control-Max-Age", value)
                self.assertEqual([n for n in notes if n is not CORS_PREFLIGHT_ONLY], expected)


class ContentRangeTest(unittest.TestCase):
    "Guards: Content-Range gives one note per rejected value, as it did with the flag."

    def test_one_note_per_rejected_value(self) -> None:
        for value, expected in [
            ("0-9/10", [CONTENT_RANGE_MISSING_UNIT]),
            ("bytes 0-9", [CONTENT_RANGE_MISSING_SLASH]),
            ("bytes */*", [CONTENT_RANGE_INVALID_ASTERISK]),
            ("bytes 0-9/x", [RANGE_INVALID_INTEGER]),
            ("bytes 0-9/", [BAD_SYNTAX]),
            ("bytes0-9/10", [BAD_SYNTAX]),
            ("bytes 0-9/10", []),
        ]:
            with self.subTest(value=value):
                notes = note_classes(FakeResponseLinter, "Content-Range", value, status_code=206)
                self.assertEqual(notes, expected)


class StrictTransportSecurityTest(unittest.TestCase):
    def counts(self, value: str) -> List[int]:
        "How many HSTS_BAD_MAX_AGE and generic syntax notes the value gets."
        notes = note_classes(FakeResponseLinter, "Strict-Transport-Security", value)
        return [
            notes.count(HSTS_BAD_MAX_AGE),
            len([n for n in notes if n in (BAD_SYNTAX, BAD_SYNTAX_DETAILED)]),
        ]

    def test_empty_max_age_gets_one_note(self) -> None:
        for value in [
            "max-age=",
            "max-age= ",
            "max-age=;",
            "max-age=; includeSubDomains",
            "max-age =;",
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), [1, 0])

    def test_second_defect_keeps_the_generic_note(self) -> None:
        for value in [
            "max-age=; foo bar",
            "max-age=;/",
            "max-age=; includeSubDomains=a b",
            "max-age=; max-age=",
            "includeSubDomains; foo bar; max-age=",
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), [1, 1])

    def test_valid_and_other_bad_values_are_unchanged(self) -> None:
        for value, expected in [
            ("max-age=1", [0, 0]),
            ("max-age", [1, 0]),
            ('max-age=""', [1, 0]),
            ("max-age=abc", [1, 0]),
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), expected)

    def test_non_empty_bad_max_age_gets_one_note(self) -> None:
        for value in [
            "max-age=1 2",
            'max-age="1',
            "max-age=1,2",
            "max-age=1\x01",
            "max-age=\x01\x02 1 2",
            "max-age=-1",
            "max-age=+1",
            "max-age=1.5",
            "max-age=0x10",
            "max-age=1 2\t",
            "max-age= 1 2 ",
            "max-age = 1 2",
            "max-age=text/html",
            "max-age=1 2; includeSubDomains",
            "includeSubDomains; max-age=1 2; preload",
            "max-age=1 2;;",
            "max-age=1 2;",
            "max-age=x; max-age=y",
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), [1, 0])

    def test_second_defect_after_non_empty_bad_max_age_keeps_the_generic_note(self) -> None:
        for value in [
            "max-age=1 2; foo bar",
            "max-age=1 2; max-age=3 4",
            "max-age=1 2; includeSubDomains=a b",
            "max-age=1 2; =x",
            "max-age=1 2;/",
            'max-age="1; foo bar',
            "max-age=1,2; max-age=",
            "foo bar; max-age=1 2",
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), [1, 1])


class SyntaxPositionTest(unittest.TestCase):
    "A specific note that replaces BAD_SYNTAX_DETAILED says where the value goes wrong."

    def rendered(
        self, linter_class: type, name: str, value: str
    ) -> List[Tuple[Type[Note], str, str]]:
        "(class, summary, detail HTML) of each top-level note."
        message = linter_class()
        message.headers.process([(name.encode(), value.encode("latin-1"))])
        message.post_checks()
        return [(type(n), str(n.summary), str(n.detail)) for n in message.notes]

    def only_note(self, linter_class: type, name: str, value: str) -> Tuple[Type[Note], str, str]:
        notes = self.rendered(linter_class, name, value)
        self.assertEqual(len(notes), 1, notes)
        return notes[0]

    def test_accept_language_specific_note_has_position(self) -> None:
        note, summary, detail = self.only_note(FakeRequestLinter, "Accept-Language", "en; foo=bar")
        self.assertIs(note, ACCEPT_LANGUAGE_BAD_SYNTAX)
        self.assertTrue(summary)
        self.assertIn("The invalid character ';' was found at position 3.", detail)
        self.assertIn("en; foo=bar\n  ^", detail)
        self.assertNotIn("<code></code>", detail)

    def test_accept_language_single_defect_has_position(self) -> None:
        for value, position in [("en;q=abc", 3), ("en;q=1.0000", 11), ("en;q=", 3)]:
            with self.subTest(value=value):
                note, summary, detail = self.only_note(FakeRequestLinter, "Accept-Language", value)
                self.assertIs(note, BAD_SYNTAX_DETAILED)
                self.assertTrue(summary)
                self.assertIn(f"found at position {position}.", detail)
                self.assertIn(value + "\n" + " " * (position - 1) + "^", detail)
                self.assertNotIn("<code></code>", detail)

    def test_position_is_within_the_list_element(self) -> None:
        notes = self.rendered(FakeRequestLinter, "Accept-Language", "de, fr; foo=bar, en")
        self.assertEqual([n for n, _, _ in notes], [ACCEPT_LANGUAGE_BAD_SYNTAX])
        detail = notes[0][2]
        self.assertIn("found at position 3.", detail)
        self.assertIn("fr; foo=bar\n  ^", detail)
        self.assertNotIn("de,", detail)

    def test_position_follows_the_right_element_with_two_bad_ones(self) -> None:
        notes = self.rendered(FakeRequestLinter, "Accept-Language", "en; foo=bar, fr;q=abc")
        self.assertEqual(
            [n for n, _, _ in notes], [ACCEPT_LANGUAGE_BAD_SYNTAX, BAD_SYNTAX_DETAILED]
        )
        self.assertIn("en; foo=bar\n  ^", notes[0][2])
        self.assertIn("fr;q=abc\n  ^", notes[1][2])

    def test_media_type_notes_have_position(self) -> None:
        for linter, name, specific in AcceptMediaTypeTest.fields:
            with self.subTest(field=name):
                note, _, detail = self.only_note(linter, name, "text/html/")
                self.assertIs(note, specific)
                self.assertIn("<code>text/html/</code> is not a valid", detail)
                self.assertIn("The invalid character '/' was found at position 10.", detail)
                self.assertIn("text/html/\n         ^", detail)

    def test_media_type_note_without_a_matching_prefix_has_no_position(self) -> None:
        for linter, name, specific in AcceptMediaTypeTest.fields:
            with self.subTest(field=name):
                note, _, detail = self.only_note(linter, name, "invalid")
                self.assertIs(note, specific)
                self.assertNotIn("position", detail)
                self.assertNotIn("<code></code>", detail)

    def test_position_is_escaped(self) -> None:
        value = "text/html/<b>`&"
        for linter, name, specific in AcceptMediaTypeTest.fields:
            with self.subTest(field=name):
                note, _, detail = self.only_note(linter, name, value)
                self.assertIs(note, specific)
                self.assertNotIn("<b>", detail)
                self.assertIn("&lt;b&gt;", detail)
                self.assertIn("found at position 10.", detail)


class _TokenList(HttpListField[ResponseLinterProtocol]):
    canonical_name = "X-Test-List"
    syntax = rfc9110.list_rule(rfc9110.token, 1)


class _TokenSingleton(SingletonField[ResponseLinterProtocol]):
    canonical_name = "X-Test-Singleton"
    syntax = rfc9110.token


class _TokenBroken(BrokenField[ResponseLinterProtocol]):
    canonical_name = "X-Test-Broken"
    syntax = rfc9110.token


class _NoSyntax(SingletonField[ResponseLinterProtocol]):
    canonical_name = "X-Test-No-Syntax"
    syntax = False


class MatchesSyntaxTest(unittest.TestCase):
    "HttpField.matches_syntax() decides one value, with the wrapper the syntax check uses."

    def check(self, field_class: type, text: str) -> bool:
        field = field_class(field_class.canonical_name, FakeResponseLinter())
        return bool(field.matches_syntax(text))

    def test_conforming(self) -> None:
        for field_class in (_TokenList, _TokenSingleton, _TokenBroken):
            with self.subTest(field=field_class.__name__):
                self.assertTrue(self.check(field_class, "foo"))

    def test_non_conforming(self) -> None:
        for field_class in (_TokenList, _TokenSingleton, _TokenBroken):
            for text in ["foo bar", 'foo"', "a=b", "\x01"]:
                with self.subTest(field=field_class.__name__, text=text):
                    self.assertFalse(self.check(field_class, text))

    def test_whitespace_around_the_text_is_allowed(self) -> None:
        for field_class in (_TokenList, _TokenSingleton, _TokenBroken):
            for text in [" foo", "foo ", "\tfoo\t", " foo \n"]:
                with self.subTest(field=field_class.__name__, text=text):
                    self.assertTrue(self.check(field_class, text))

    def test_empty_and_blank(self) -> None:
        for field_class in (_TokenList, _TokenSingleton, _TokenBroken):
            for text in ["", " "]:
                with self.subTest(field=field_class.__name__, text=text):
                    self.assertFalse(self.check(field_class, text))

    def test_list_fields_are_checked_per_element(self) -> None:
        self.assertFalse(self.check(_TokenList, "foo, bar"))

    def test_field_without_syntax_accepts_anything(self) -> None:
        for text in ["", "anything at all", "\x01"]:
            with self.subTest(text=text):
                self.assertTrue(self.check(_NoSyntax, text))


if __name__ == "__main__":
    unittest.main()
