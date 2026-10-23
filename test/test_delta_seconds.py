import unittest
from typing import Any, Dict, List, Tuple, Type

from httplint.field.utils import is_negative_integer, parse_delta_seconds, parse_digits
from httplint.message import REQUEST_TARGET_FORM, HttpRequestLinter
from httplint.note import Note


class BAD(Note):
    _summary = "bad"
    _text = "bad"


class TestParseDeltaSeconds(unittest.TestCase):
    def run_parse(
        self, value: str, **kw: Any
    ) -> Tuple[Any, List[Tuple[Type[Note], Dict[str, Any]]]]:
        notes: List[Tuple[Type[Note], Dict[str, Any]]] = []

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
        self.assertEqual(self.run_parse("9" * 100_000, max_digits=4000), (None, [(BAD, {})]))
        self.assertEqual(self.run_parse("0" * 100_000, max_digits=4000), (0, []))
        self.assertEqual(self.run_parse("_" * 100_000, max_digits=4000), (None, [(BAD, {})]))

    def test_parse_digits(self) -> None:
        self.assertEqual(parse_digits("0" * 5000 + "443", max_digits=5), 443)
        self.assertEqual(parse_digits("99999", max_digits=5), 99999)
        for value in ["", "-1", "+1", "1_0", "999999", "٥"]:
            self.assertIsNone(parse_digits(value, max_digits=5), repr(value))

    def test_is_negative_integer(self) -> None:
        for value in ["-1", "-0", "-" + "9" * 5000]:
            self.assertTrue(is_negative_integer(value), value)
        for value in ["", "-", "1", "+1", "--1", "-1_0", "- 1", "-٥"]:
            self.assertFalse(is_negative_integer(value), repr(value))


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


if __name__ == "__main__":
    unittest.main()
