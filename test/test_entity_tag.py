"""
parse_entity_tag must decode (weak, opaque-tag), treat "W/" as case-sensitive, and report
a lower-case "w/" once.
"""

import unittest
from typing import Any, List, Type

from httplint.field.utils import ENTITY_TAG_WEAK_CASE, parse_entity_tag
from httplint.note import Note


def parse(value: str) -> Any:
    notes: List[Type[Note]] = []

    def add_note(note: Type[Note], **kwargs: Any) -> None:
        notes.append(note)

    try:
        result = parse_entity_tag(value, add_note)
    except ValueError:
        result = None
    return result, notes


class EntityTagTest(unittest.TestCase):
    def test_strong(self) -> None:
        self.assertEqual(parse('"foo"'), ((False, "foo"), []))

    def test_weak(self) -> None:
        self.assertEqual(parse('W/"foo"'), ((True, "foo"), []))

    def test_escaped(self) -> None:
        self.assertEqual(parse(r'"a\"b"'), ((False, 'a"b'), []))

    def test_lower_case_weak_is_one_note(self) -> None:
        self.assertEqual(parse('w/"foo"'), (None, [ENTITY_TAG_WEAK_CASE]))

    def test_lower_case_weak_with_other_defect_is_left_to_syntax_check(self) -> None:
        self.assertEqual(parse("w/foo"), (None, []))

    def test_lower_case_weak_suppresses_the_syntax_note(self) -> None:
        calls: List[bool] = []
        with self.assertRaises(ValueError):
            parse_entity_tag('w/"foo"', lambda note, **kwargs: None, lambda: calls.append(True))
        self.assertEqual(calls, [True])

    def test_other_defects_do_not_suppress_the_syntax_note(self) -> None:
        calls: List[bool] = []
        for value in ["w/foo", 'w/"foo', '"foo"', 'W/"foo"']:
            try:
                parse_entity_tag(value, lambda note, **kwargs: None, lambda: calls.append(True))
            except ValueError:
                pass
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
