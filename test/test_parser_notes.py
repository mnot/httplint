"""
Checks on the notes that individual field parsers emit, beyond which classes appear.
"""

import unittest
from typing import List

from httplint import HttpResponseLinter
from httplint.field.parsers.permissions_policy import PERMISSIONS_POLICY_UNKNOWN_TOKEN
from httplint.field.parsers.use_as_dictionary import USE_AS_DICTIONARY_BAD_TYPE
from httplint.field.parsers.x_frame_options import FRAME_OPTIONS_UNKNOWN
from httplint.note import Note


def _notes(headers: List[tuple]) -> List[Note]:
    "All notes, with sub-notes flattened in."
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(headers)
    linter.finish_content(True)
    out: List[Note] = []
    pending = list(linter.notes)
    while pending:
        note = pending.pop(0)
        out.append(note)
        pending.extend(note.subnotes)
    return out


class PermissionsPolicyUnknownTokenTextTest(unittest.TestCase):
    def test_text_lists_wildcard_as_valid(self) -> None:
        notes = [
            n
            for n in _notes([(b"Permissions-Policy", b"geolocation=(self foo)")])
            if isinstance(n, PERMISSIONS_POLICY_UNKNOWN_TOKEN)
        ]
        self.assertEqual(len(notes), 1)
        detail = str(notes[0].detail)
        self.assertIn("foo", detail)
        self.assertIn("Valid tokens are", detail)
        self.assertIn("<code>*</code>", detail)


class UseAsDictionaryBadTypeKeyTest(unittest.TestCase):
    def test_note_names_the_key(self) -> None:
        notes = [
            n
            for n in _notes([(b"Use-As-Dictionary", b'match=123, id=456, type="raw"')])
            if isinstance(n, USE_AS_DICTIONARY_BAD_TYPE)
        ]
        self.assertEqual(sorted(n.vars["param"] for n in notes), ["id", "match", "type"])
        for note in notes:
            self.assertNotIn("123", str(note.summary))
            self.assertNotIn("456", str(note.summary))


class AllowFromXFOTest(unittest.TestCase):
    def test_allow_from_is_unknown(self) -> None:
        notes = _notes([(b"X-Frame-Options", b"ALLOW-FROM https://deny.example.com")])
        classes = [n.__class__ for n in notes]
        self.assertIn(FRAME_OPTIONS_UNKNOWN, classes)
        self.assertEqual(
            [c.__name__ for c in classes if c.__name__.startswith("FRAME_OPTIONS")],
            ["FRAME_OPTIONS_UNKNOWN"],
        )


if __name__ == "__main__":
    unittest.main()
