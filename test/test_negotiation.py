"""
parse_qvalue and vary_covers, the shared content negotiation helpers.
"""

import unittest
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

from httplint.field.utils import BAD_Q_VALUE, parse_qvalue, vary_covers
from httplint.types import ParamDictType


class ParseQvalueTest(unittest.TestCase):
    def parse(self, q_str: Optional[str], raw: str = "") -> Tuple[Optional[float], List[Any]]:
        params: ParamDictType = {} if q_str is None else {"q": q_str}
        notes: List[Any] = []

        def add_note(note: Any, **vrs: Any) -> None:
            notes.append(note(f"{note.__name__}", **vrs))

        result = parse_qvalue(params, add_note, raw, item="en")
        self.assertNotIn("q", params)
        return result, notes

    def test_absent(self) -> None:
        self.assertEqual(self.parse(None), (None, []))

    def test_valid(self) -> None:
        for q_str, expected in [
            ("0", 0.0),
            ("1", 1.0),
            ("0.", 0.0),
            ("1.", 1.0),
            ("0.5", 0.5),
            ("0.123", 0.123),
            ("1.000", 1.0),
            ("1.0", 1.0),
        ]:
            with self.subTest(q=q_str):
                self.assertEqual(self.parse(q_str), (expected, []))

    def test_invalid(self) -> None:
        for q_str in ["+1", "-0", "1e0", ".5", "abc", "", "1.5", "2", "0.1234", "1.001", " 1", "1 "]:
            with self.subTest(q=q_str):
                result, notes = self.parse(q_str)
                self.assertIsNone(result)
                self.assertEqual(len(notes), 1)
                self.assertIsInstance(notes[0], BAD_Q_VALUE)

    def test_none_value(self) -> None:
        notes: List[Any] = []
        params: ParamDictType = {"q": None}
        self.assertIsNone(parse_qvalue(params, lambda note, **vrs: notes.append(note)))
        self.assertEqual(notes, [BAD_Q_VALUE])

    def test_quoted(self) -> None:
        result, notes = self.parse("0.5", ' q="0.5"')
        self.assertIsNone(result)
        self.assertEqual(len(notes), 1)

    def test_quoted_only_first_q_counts(self) -> None:
        # parse_params keeps the first instance of a repeated parameter.
        self.assertEqual(self.parse("0.5", ' q=0.5; q="1"'), (0.5, []))

    def test_unquoted_raw(self) -> None:
        self.assertEqual(self.parse("0.5", "foo=bar; q=0.5"), (0.5, []))

    def test_summary_renders_item(self) -> None:
        _, notes = self.parse("abc")
        self.assertEqual(notes[0].summary, "The q value on 'en' is invalid.")
        self.assertNotIn("{", notes[0].summary)
        self.assertNotIn("%", notes[0].summary)
        self.assertTrue(notes[0].detail)

    def test_no_note(self) -> None:
        params: ParamDictType = {"q": "abc"}
        self.assertIsNone(parse_qvalue(params, None))
        self.assertNotIn("q", params)


def message_with_vary(vary: Any) -> Any:
    parsed = {} if vary is None else {"vary": vary}
    return SimpleNamespace(headers=SimpleNamespace(parsed=parsed))


class VaryCoversTest(unittest.TestCase):
    def test_no_vary(self) -> None:
        self.assertFalse(vary_covers(message_with_vary(None), "sec-ch-ua"))
        self.assertFalse(vary_covers(message_with_vary([]), "sec-ch-ua"))

    def test_listed(self) -> None:
        message = message_with_vary(["accept-encoding", "sec-ch-ua"])
        self.assertTrue(vary_covers(message, "sec-ch-ua"))
        self.assertFalse(vary_covers(message, "sec-ch-ua-mobile"))

    def test_case_insensitive(self) -> None:
        self.assertTrue(vary_covers(message_with_vary(["sec-ch-ua"]), "Sec-CH-UA"))

    def test_star(self) -> None:
        self.assertTrue(vary_covers(message_with_vary(["*"]), "anything"))

    def test_set(self) -> None:
        self.assertTrue(vary_covers(message_with_vary({"available-dictionary"}), "Available-Dictionary"))


if __name__ == "__main__":
    unittest.main()
