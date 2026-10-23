"""
Content-Security-Policy syntax checking must be linear-time, and report-to problems must be
attached to the header that has them.
"""

import time
import unittest
from functools import partial
from typing import List, Tuple

from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.parsers.content_security_policy import (
    CONTENT_SECURITY_POLICY,
    CSP_REPORT_TO_MISSING,
)
from httplint.field.tests import FakeResponseLinter
from httplint.note import Note

# Generous: linear inputs take well under a second; the old regex took seconds to minutes.
TIME_LIMIT = 2.0


def process(headers: List[Tuple[bytes, bytes]]) -> FakeResponseLinter:
    message = FakeResponseLinter()
    message.headers.process(headers)
    message.post_checks()
    for handler in message.headers.handlers.values():
        field_add_note = partial(
            message.notes.add,
            f"field-{handler.canonical_name.lower()}",
            field_name=handler.canonical_name,
        )
        handler.post_check(field_add_note)
    return message


class CSPBacktrackingTest(unittest.TestCase):
    def assert_fast(self, value: bytes) -> None:
        for name in (b"Content-Security-Policy", b"Content-Security-Policy-Report-Only"):
            with self.subTest(name=name, value=value[:30]):
                start = time.monotonic()
                process([(name, value)])
                self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def test_trailing_whitespace_then_bad_byte(self) -> None:
        self.assert_fast(b"a" + b" " * 2000 + b"\x80")

    def test_repeated_directives_then_bad_byte(self) -> None:
        self.assert_fast(b"a b ;" * 40 + b"\x80")

    def test_mixed_whitespace_then_bad_byte(self) -> None:
        self.assert_fast(b"a" + b" \t" * 1000 + b"\x80")


def has_report_to_child(note: Note) -> bool:
    return any(isinstance(n, CSP_REPORT_TO_MISSING) for n in note.subnotes)


class CSPReportToAttributionTest(unittest.TestCase):
    def assert_attribution(self, headers: List[Tuple[bytes, bytes]]) -> None:
        message = process(headers)
        parents = [n for n in message.notes if isinstance(n, CONTENT_SECURITY_POLICY)]
        self.assertEqual(len(parents), 2)
        with_child = [p for p in parents if has_report_to_child(p)]
        self.assertEqual(len(with_child), 1)
        self.assertIn("reporting only", with_child[0].summary)

    def test_enforced_header_first(self) -> None:
        self.assert_attribution(
            [
                (b"Content-Security-Policy", b"script-src 'self'"),
                (b"Content-Security-Policy-Report-Only", b"script-src 'self'; report-to rep"),
            ]
        )

    def test_report_only_header_first(self) -> None:
        self.assert_attribution(
            [
                (b"Content-Security-Policy-Report-Only", b"script-src 'self'; report-to rep"),
                (b"Content-Security-Policy", b"script-src 'self'"),
            ]
        )


class CSPSyntaxPositionTest(unittest.TestCase):
    """BAD_SYNTAX_DETAILED must blame the offending byte, not whitespace before it."""

    def problem(self, value: bytes) -> str:
        message = process([(b"Content-Security-Policy", value)])
        problems = [
            str(n.vars["problem"]) for n in message.notes if isinstance(n, BAD_SYNTAX_DETAILED)
        ]
        self.assertEqual(len(problems), 1)
        return problems[0]

    def test_after_value(self) -> None:
        self.assertEqual(
            self.problem(b"script-src 'self' \x80"),
            "The invalid character '\x80' was found at position 19.",
        )

    def test_after_name(self) -> None:
        self.assertEqual(
            self.problem(b"script-src \t\x80"),
            "The invalid character '\x80' was found at position 13.",
        )

    def test_after_semicolon(self) -> None:
        self.assertEqual(
            self.problem(b"script-src 'self'; \x80"),
            "The invalid character ' ' was found at position 19.",
        )


if __name__ == "__main__":
    unittest.main()
