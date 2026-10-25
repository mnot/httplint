"""
split_params_off splits a field value at its first ";" into a head and parameter text, in linear
time, exactly as the "split(';', 1)" blocks it replaced did.

The tests marked as guards pass on main too: the helper is a pure refactor.
"""

import itertools
import time
import unittest

from httplint.field.params import split_params_off
from httplint.field.utils import parse_media_type

# Generous: linear inputs take milliseconds.
TIME_LIMIT = 2.0
SIZE = 1_000_000


def old_split(value):
    "The block that was copied into four parsers."
    try:
        head, param_str = value.split(";", 1)
    except ValueError:
        head, param_str = value, ""
    return head, param_str


class SplitParamsOffTest(unittest.TestCase):
    def test_no_semicolon(self):
        self.assertEqual(split_params_off(""), ("", ""))
        self.assertEqual(split_params_off("gzip"), ("gzip", ""))

    def test_params(self):
        self.assertEqual(split_params_off("gzip;q=0.5"), ("gzip", "q=0.5"))
        self.assertEqual(split_params_off("gzip ; q=0.5"), ("gzip", " q=0.5"))
        self.assertEqual(split_params_off("a;b=c;d=e"), ("a", "b=c;d=e"))

    def test_head_whitespace(self):
        "The grammars allow OWS before the ';', so it isn't part of the head (#330)."
        self.assertEqual(split_params_off("gzip ; q=0.5"), ("gzip", " q=0.5"))
        self.assertEqual(split_params_off("gzip\t;\tq=0.5"), ("gzip", "\tq=0.5"))
        self.assertEqual(split_params_off("gzip \t ;q=0.5"), ("gzip", "q=0.5"))
        self.assertEqual(split_params_off(" gzip ;q=0.5"), ("gzip", "q=0.5"))
        self.assertEqual(split_params_off("gzip "), ("gzip", ""))
        self.assertEqual(split_params_off(" ; q=1"), ("", " q=1"))

    def test_empty_parts(self):
        self.assertEqual(split_params_off(";"), ("", ""))
        self.assertEqual(split_params_off(";;"), ("", ";"))
        self.assertEqual(split_params_off(";q=1"), ("", "q=1"))
        self.assertEqual(split_params_off("a;;b"), ("a", ";b"))

    def test_trailing_semicolon(self):
        self.assertEqual(split_params_off("a;"), ("a", ""))
        self.assertEqual(split_params_off("a;b=c;"), ("a", "b=c;"))

    def test_first_semicolon_wins_inside_quotes(self):
        "Quotes aren't tracked: a head is never a quoted-string, and the rest goes to parse_params."
        self.assertEqual(split_params_off('a;b="c;d"'), ("a", 'b="c;d"'))
        self.assertEqual(split_params_off('"a;b";c=d'), ('"a', 'b";c=d'))
        self.assertEqual(split_params_off(r'a;b="c\";d"'), ("a", r'b="c\";d"'))
        self.assertEqual(split_params_off('a;b="c;d'), ("a", 'b="c;d'))

    def test_parameters_keep_quoted_semicolons(self):
        "Guard: parse_media_type hands the quoted semicolon to the parameter parser intact."
        notes = []
        media_type, params = parse_media_type(
            'text/html;a="b;c";d=e', lambda note, *_, **__: notes.append(note)
        )
        self.assertEqual(media_type, "text/html")
        self.assertEqual(params, {"a": "b;c", "d": "e"})
        self.assertEqual(notes, [])

    def test_matches_old_split(self):
        """
        Guard: same result as the replaced blocks, for every short string over a small alphabet,
        apart from the whitespace now stripped from the head.
        """
        for length in range(7):
            for chars in itertools.product('a;="\\ ', repeat=length):
                value = "".join(chars)
                head, param_str = old_split(value)
                self.assertEqual(split_params_off(value), (head.strip(), param_str), value)

    def test_linear_time(self):
        for value in (
            "a" * SIZE,
            ";" * SIZE,
            "a;" * (SIZE // 2),
            'a;b="c;' * (SIZE // 7),
            "\\" * SIZE + ";",
            '"' * SIZE + ";" + '"' * SIZE,
        ):
            start = time.monotonic()
            head, param_str = split_params_off(value)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, TIME_LIMIT)
            self.assertEqual(len(head) + len(param_str) + (1 if ";" in value else 0), len(value))


if __name__ == "__main__":
    unittest.main()
