import time
import unittest
from typing import Any, List, Tuple, Type

from httplint.field.utils import parse_delta_seconds
from httplint.message import REQUEST_TARGET_FORM, HttpRequestLinter
from httplint.note import Note


class BAD(Note):
    _summary = "bad"
    _text = "bad"


class TestParseDeltaSeconds(unittest.TestCase):
    def run_parse(self, value: str, **kw: Any) -> Tuple[Any, List[Tuple[Type[Note], dict]]]:
        notes: List[Tuple[Type[Note], dict]] = []

        def add_note(note: Type[Note], category: Any = None, **vrs: Any) -> Any:
            notes.append((note, vrs))

        return parse_delta_seconds(value, add_note, BAD, **kw), notes

    def test_valid(self) -> None:
        for value, expected in [("0", 0), ("10", 10), ("007", 7), ("0" * 5000 + "5", 5)]:
            self.assertEqual(self.run_parse(value), (expected, []), value)

    def test_invalid(self) -> None:
        for value in ["", "+5", "-1", "-0", "1_0", " 1", "1 ", "1.0", "0x10", "a", "٥"]:
            self.assertEqual(self.run_parse(value), (None, [(BAD, {})]), repr(value))

    def test_max_digits(self) -> None:
        self.assertEqual(self.run_parse("9" * 20), (int("9" * 20), []))
        self.assertEqual(self.run_parse("9" * 21), (None, [(BAD, {})]))
        self.assertEqual(self.run_parse("9" * 5, max_digits=5), (99999, []))
        self.assertEqual(self.run_parse("9" * 6, max_digits=5), (None, [(BAD, {})]))

    def test_note_vars(self) -> None:
        self.assertEqual(self.run_parse("x", ref_uri="u"), (None, [(BAD, {"ref_uri": "u"})]))

    def test_huge_value(self) -> None:
        start = time.perf_counter()
        for value in ["9" * 100_000, "0" * 100_000, "_" * 100_000]:
            self.run_parse(value, max_digits=4000)
        self.assertLess(time.perf_counter() - start, 1.0)


class TestConnectLongPort(unittest.TestCase):
    def lint(self, target: bytes) -> HttpRequestLinter:
        linter = HttpRequestLinter()
        linter.process_request_topline(b"CONNECT", target, b"1.1")
        return linter

    def test_long_port_does_not_crash(self) -> None:
        for port in [b"9" * 5000, b"9" * 100_000, b"1" + b"0" * 5000]:
            linter = self.lint(b"example.com:" + port)
            self.assertIn(REQUEST_TARGET_FORM, {type(n) for n in linter.notes})

    def test_leading_zeros_ok(self) -> None:
        linter = self.lint(b"example.com:" + b"0" * 5000 + b"443")
        self.assertNotIn(REQUEST_TARGET_FORM, {type(n) for n in linter.notes})
