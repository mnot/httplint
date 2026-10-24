"""
Proxy-Status and Cache-Status members must be a String or Token (RFC 9209 and RFC 9211,
Section 2); other member types get one note, and render as plain text.
"""

import unittest
from typing import List, Tuple

from httplint.field.parsers.cache_status import CACHE_STATUS, CACHE_STATUS_BAD_MEMBER
from httplint.field.parsers.proxy_status import PROXY_STATUS, PROXY_STATUS_BAD_MEMBER
from httplint.message import HttpResponseLinter
from httplint.note import Note

HTML = "<img src=x onerror=alert(1)>"

# wire value, expected type name, expected rendering of the member
BAD_MEMBERS: List[Tuple[bytes, str, str]] = [
    (b"(a b)", "Inner List", "(a b)"),
    (b"(a b);x=1", "Inner List", "(a b)"),
    (b"()", "Inner List", "()"),
    (b"42", "Integer", "42"),
    (b"1.5", "Decimal", "1.5"),
    (b"?1", "Boolean", "True"),
    (b"?0", "Boolean", "False"),
    (b":YWJj:", "Byte Sequence", "abc"),
]

FIELDS = [
    (b"Proxy-Status", PROXY_STATUS, PROXY_STATUS_BAD_MEMBER),
    (b"Cache-Status", CACHE_STATUS, CACHE_STATUS_BAD_MEMBER),
]


def notes_for(name: bytes, value: bytes) -> List[Note]:
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(name, value)])
    linter.finish_content(True)
    return list(linter.notes)


class MemberTypeTest(unittest.TestCase):
    def test_bad_members_render(self) -> None:
        for name, status_note, bad_note in FIELDS:
            for wire, type_name, shown in BAD_MEMBERS:
                with self.subTest(field=name, wire=wire):
                    notes = notes_for(name, wire)
                    bad = [n for n in notes if isinstance(n, bad_note)]
                    self.assertEqual(len(bad), 1)
                    self.assertIn(type_name, str(bad[0].summary))
                    self.assertIn(f"<code>{shown}</code>", str(bad[0].detail))
                    self.assertIn(type_name, str(bad[0].detail))
                    status = [n for n in notes if isinstance(n, status_note)]
                    self.assertEqual(len(status), 1)
                    self.assertIn(f"<strong><code>{shown}</code></strong>", str(status[0].detail))
                    self.assertNotIn("(Token", str(status[0].detail))
                    self.assertNotIn("{", str(status[0].detail))

    def test_display_string_member(self) -> None:
        for name, _, bad_note in FIELDS:
            with self.subTest(field=name):
                bad = [n for n in notes_for(name, b'%"a"') if isinstance(n, bad_note)]
                self.assertEqual(len(bad), 1)
                self.assertIn("Display String", str(bad[0].summary))

    def test_empty_display_string_has_no_empty_code_span(self) -> None:
        for name, _, bad_note in FIELDS:
            with self.subTest(field=name):
                bad = [n for n in notes_for(name, b'%""') if isinstance(n, bad_note)]
                self.assertEqual(len(bad), 1)
                self.assertNotIn("<code></code>", str(bad[0].detail))
                self.assertIn("(empty)", str(bad[0].detail))

    def test_string_and_token_members_not_flagged(self) -> None:
        for name, _, bad_note in FIELDS:
            for wire in (b"a", b'"a b"', b'""', b"a, b", b'a; hit, "b"'):
                with self.subTest(field=name, wire=wire):
                    self.assertFalse(
                        [n for n in notes_for(name, wire) if isinstance(n, bad_note)]
                    )

    def test_one_bad_member_among_good(self) -> None:
        for name, status_note, bad_note in FIELDS:
            with self.subTest(field=name):
                notes = notes_for(name, b'a, (b c), "d", e')
                bad = [n for n in notes if isinstance(n, bad_note)]
                self.assertEqual(len(bad), 1)
                self.assertIn("(b c)", str(bad[0].detail))
                status = [n for n in notes if isinstance(n, status_note)]
                self.assertEqual(len(status), 1)

    def test_one_note_per_defect(self) -> None:
        for name, status_note, bad_note in FIELDS:
            with self.subTest(field=name):
                classes = [
                    n.__class__
                    for n in notes_for(name, b"(a b)")
                    if n.__class__.__name__.startswith(name.decode().upper().replace("-", "_"))
                ]
                self.assertEqual(classes, [bad_note, status_note])

    def test_member_values_are_escaped(self) -> None:
        for name, _, _ in FIELDS:
            with self.subTest(field=name):
                detail = "".join(str(n.detail) for n in notes_for(name, f'(a "{HTML}")'.encode()))
                self.assertNotIn("<img", detail)
                self.assertIn("&lt;img", detail)


if __name__ == "__main__":
    unittest.main()
