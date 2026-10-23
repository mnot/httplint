"""
Fields that report a syntax defect with a specific note give that defect one note; a value with a
second, unrelated syntax defect still gets the generic syntax note.
"""

import unittest
from functools import partial
from typing import Iterable, List, Type

from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.parsers.accept import ACCEPT_BAD_SYNTAX
from httplint.field.parsers.accept_language import ACCEPT_LANGUAGE_BAD_SYNTAX
from httplint.field.parsers.accept_patch import ACCEPT_PATCH_BAD_SYNTAX
from httplint.field.parsers.accept_post import ACCEPT_POST_BAD_SYNTAX
from httplint.field.parsers.access_control_max_age import (
    CORS_MAX_AGE_INVALID,
    CORS_MAX_AGE_NEGATIVE,
)
from httplint.field.parsers.content_range import (
    CONTENT_RANGE_INVALID_ASTERISK,
    CONTENT_RANGE_MISSING_SLASH,
    CONTENT_RANGE_MISSING_UNIT,
    RANGE_INVALID_INTEGER,
)
from httplint.field.parsers.strict_transport_security import HSTS_BAD_MAX_AGE
from httplint.field.parsers.age import AGE_NEGATIVE, AGE_NOT_INT
from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.tests import FakeRequestLinter, FakeResponseLinter
from httplint.i18n import L_
from httplint.note import Note


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
            for value in ["invalid; a", "invalid; a=b c", "invalid; =b"]:
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
        for value in ["en; foo=bar; q=abc", "e n; foo=bar", "en; foo=bar; q=1; q=0.5", ";foo=bar"]:
            with self.subTest(value=value):
                notes = self.notes(value)
                self.assertIn(ACCEPT_LANGUAGE_BAD_SYNTAX, notes)
                self.assertEqual(len([n for n in notes if n in (BAD_SYNTAX, BAD_SYNTAX_DETAILED)]), 1)

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
        for value in ["max-age=", "max-age= ", "max-age=;", "max-age=; includeSubDomains", "max-age =;"]:
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
            ("max-age=1 2", [1, 1]),
        ]:
            with self.subTest(value=value):
                self.assertEqual(self.counts(value), expected)


if __name__ == "__main__":
    unittest.main()
