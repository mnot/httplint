"""
Proxy-Status and Cache-Status members must be a String or Token (RFC 9209 and RFC 9211,
Section 2); other member types get one note, and render in wire form.
"""

import html
import unittest
from typing import List, Tuple

from httplint.field.parsers.cache_status import (
    CACHE_STATUS,
    CACHE_STATUS_BAD_MEMBER,
    CACHE_STATUS_BAD_PARAM_VAL,
)
from httplint.field.parsers.proxy_status import (
    PROXY_STATUS,
    PROXY_STATUS_BAD_MEMBER,
    PROXY_STATUS_BAD_PARAM_VAL,
)
from httplint.message import HttpResponseLinter
from httplint.note import Note

HTML = "<img src=x onerror=alert(1)>"

# wire value, expected type phrase, expected rendering of the member (its wire form)
BAD_MEMBERS: List[Tuple[bytes, str, str]] = [
    (b"(a b)", "an Inner List", "(a b)"),
    (b"(a b);x=1", "an Inner List", "(a b)"),
    (b"(a;x=1 b)", "an Inner List", "(a;x=1 b)"),
    (b"(1 ?1)", "an Inner List", "(1 ?1)"),
    (b'("")', "an Inner List", '("")'),
    (b'(a "")', "an Inner List", '(a "")'),
    (b"()", "an Inner List", "()"),
    (b"42", "an Integer", "42"),
    (b"1.5", "a Decimal", "1.5"),
    (b"?1", "a Boolean", "?1"),
    (b"?0", "a Boolean", "?0"),
    (b":YWJj:", "a Byte Sequence", ":YWJj:"),
    (b"::", "a Byte Sequence", "::"),
    (b"@1659578233", "a Date", "@1659578233"),
    (b'%"a"', "a Display String", '%"a"'),
    (b'%""', "a Display String", '%""'),
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
            for wire, type_phrase, shown in BAD_MEMBERS:
                with self.subTest(field=name, wire=wire):
                    notes = notes_for(name, wire)
                    bad = [n for n in notes if isinstance(n, bad_note)]
                    self.assertEqual(len(bad), 1)
                    self.assertIn(f"is {type_phrase}, not a String or Token", str(bad[0].summary))
                    detail = html.unescape(str(bad[0].detail))
                    self.assertIn(f"<code>{shown}</code>", detail)
                    self.assertIn(f"is {type_phrase}.", detail)
                    status = [n for n in notes if isinstance(n, status_note)]
                    self.assertEqual(len(status), 1)
                    status_detail = html.unescape(str(status[0].detail))
                    self.assertIn(f"<strong><code>{shown}</code></strong>", status_detail)
                    self.assertNotIn("(Token", status_detail)
                    self.assertNotIn("{", status_detail)
                    self.assertNotIn("<code></code>", detail + status_detail)

    def test_no_wrong_article(self) -> None:
        for name, _, bad_note in FIELDS:
            for wire, _, _ in BAD_MEMBERS:
                with self.subTest(field=name, wire=wire):
                    bad = [n for n in notes_for(name, wire) if isinstance(n, bad_note)]
                    self.assertNotRegex(str(bad[0].summary), r"\b[Aa] [AEIOU]")
                    self.assertNotRegex(str(bad[0].detail), r"\b[Aa] [AEIOU]")

    def test_bad_member_parameters_still_checked(self) -> None:
        for name, bad_param, bad_note in (
            (b"Cache-Status", b"hit=5", CACHE_STATUS_BAD_PARAM_VAL),
            (b"Proxy-Status", b"next-protocol=1", PROXY_STATUS_BAD_PARAM_VAL),
        ):
            with self.subTest(field=name):
                classes = [n.__class__ for n in notes_for(name, b"1; " + bad_param)]
                self.assertEqual(classes.count(bad_note), 1)
                self.assertEqual(
                    sum(1 for c in classes if c.__name__.endswith("_BAD_MEMBER")),
                    1,
                )

    def test_string_and_token_members_not_flagged(self) -> None:
        for name, _, bad_note in FIELDS:
            for wire in (b"a", b'"a b"', b'""', b"a, b", b'a; hit, "b"'):
                with self.subTest(field=name, wire=wire):
                    self.assertFalse([n for n in notes_for(name, wire) if isinstance(n, bad_note)])

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
