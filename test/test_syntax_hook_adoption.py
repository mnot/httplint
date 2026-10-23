"""
Fields that report a syntax defect with a specific note give that defect one note; a value with a
second, unrelated syntax defect still gets the generic syntax note.
"""

import unittest
from typing import List, Type

from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.parsers.accept import ACCEPT_BAD_SYNTAX
from httplint.field.parsers.accept_language import ACCEPT_LANGUAGE_BAD_SYNTAX
from httplint.field.parsers.accept_patch import ACCEPT_PATCH_BAD_SYNTAX
from httplint.field.parsers.accept_post import ACCEPT_POST_BAD_SYNTAX
from httplint.field.tests import FakeRequestLinter, FakeResponseLinter
from httplint.note import Note


def note_classes(linter_class: type, name: str, *values: str) -> List[Type[Note]]:
    "The classes of the notes the message gets for these field lines, in order."
    message = linter_class()
    message.headers.process([(name.encode(), value.encode("latin-1")) for value in values])
    message.post_checks()
    return [type(note) for note in message.notes]


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


if __name__ == "__main__":
    unittest.main()
