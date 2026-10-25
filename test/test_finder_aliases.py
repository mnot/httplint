"""
Every entry in HttpFieldFinder.field_aliases must resolve, through the real lookup, to the parser
it names. Keys that are not in name_token() form (e.g. hyphenated), or that find_module refuses,
silently resolve to UnknownHttpField.
"""

import sys
import unittest
from typing import Dict, List

from httplint.field.finder import HttpFieldFinder, UnknownHttpField
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import Note


def wire_names(key: str) -> List[str]:
    "Spellings of a field name that normalise to the alias key."
    return sorted({key, key.replace("_", "-"), key.upper(), key.replace("_", "-").title()})


def request_note_names(name: str) -> List[str]:
    req = HttpRequestLinter()
    req.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
    req.process_headers([(name.encode("ascii"), b"x")])
    req.feed_content(b"")
    req.finish_content(True)
    return sorted(note_name(n) for n in req.notes)


def response_note_names(name: str) -> List[str]:
    res = HttpResponseLinter()
    res.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    res.process_headers([(name.encode("ascii"), b"x")])
    res.feed_content(b"")
    res.finish_content(True)
    return sorted(note_name(n) for n in res.notes)


def note_name(note: Note) -> str:
    return note.__class__.__name__


class FinderAliasTest(unittest.TestCase):
    def test_table_is_in_lookup_form(self) -> None:
        "Keys and targets are what name_token() produces; anything else can never match."
        for key, target in HttpFieldFinder.field_aliases.items():
            with self.subTest(key=key):
                self.assertEqual(HttpFieldFinder.name_token(key), key)
                self.assertEqual(HttpFieldFinder.name_token(target), target)

    def test_every_alias_resolves_to_its_target(self) -> None:
        for key, target in HttpFieldFinder.field_aliases.items():
            module = sys.modules[f"httplint.field.parsers.{target}"]
            expected = getattr(module, target)
            for name in wire_names(key):
                with self.subTest(key=key, name=name):
                    self.assertIs(HttpFieldFinder.find_handler_class(name), expected)
                    self.assertIs(HttpFieldFinder.find_module(name), module)
                    handler = HttpFieldFinder(HttpRequestLinter()).find_handler(name)
                    self.assertIs(type(handler), expected)
                    self.assertNotIsInstance(handler, UnknownHttpField)

    def test_alias_targets_are_not_aliases(self) -> None:
        "Lookup resolves one level only."
        for key, target in HttpFieldFinder.field_aliases.items():
            with self.subTest(key=key):
                self.assertNotIn(target, HttpFieldFinder.field_aliases)

    def test_alias_targets_not_underscore_prefixed(self) -> None:
        "find_module applies aliases before its leading-underscore guard; that is only safe if no target is special."
        for key, target in HttpFieldFinder.field_aliases.items():
            with self.subTest(key=key):
                self.assertFalse(target.startswith("_"))

    def test_x_pad_aliases_match_x_pad(self) -> None:
        "Resolving the X-Pad aliases gives the same notes as X-Pad itself."
        expected = response_note_names("X-Pad")
        self.assertIn("FIELD_DEPRECATED", expected)
        expected_req = request_note_names("X-Pad")
        self.assertIn("RESPONSE_HDR_IN_REQUEST", expected_req)
        for key, target in HttpFieldFinder.field_aliases.items():
            if target == "x_pad":
                name = key.replace("_", "-")
                with self.subTest(key=key):
                    self.assertEqual(response_note_names(name), expected)
                    self.assertEqual(request_note_names(name), expected_req)

    def test_previously_working_aliases(self) -> None:
        "Guard: aliases that resolved before the table was normalised still do."
        expected: Dict[str, str] = {
            "Nncoection": "connectiox",
            "Cneonction": "connectiox",
            "yyyyyyyyyy": "connectiox",
            "XXXXXXXXXX": "connectiox",
            "X_cnection": "connectiox",
            "X-Cnection": "connectiox",
            "From": "from_field",
        }
        for name, module_name in expected.items():
            with self.subTest(name=name):
                cls = HttpFieldFinder.find_handler_class(name)
                self.assertIsNotNone(cls)
                assert cls is not None
                self.assertEqual(cls.__name__, module_name)

    def test_leading_underscore_still_special(self) -> None:
        "The leading-underscore guard still applies to names that are not aliases."
        self.assertIsNone(HttpFieldFinder.find_module("__init__"))
        self.assertIsNone(HttpFieldFinder.find_handler_class("_foo"))
        self.assertIsNone(HttpFieldFinder.find_handler_class("__builtins__"))


if __name__ == "__main__":
    unittest.main()
