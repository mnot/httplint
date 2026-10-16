"""
split_list_field must split on commas outside quoted-strings, in linear time.

It used to be a regex that backtracked quadratically on some inputs.
"""

import time
import unittest

from httplint.field.utils import split_list_field

# Generous: linear inputs take well under a second; the quadratic ones took minutes.
TIME_LIMIT = 5.0
SIZE = 100_000


class SplitListFieldTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(split_list_field(""), [])
        self.assertEqual(split_list_field("a"), ["a"])
        self.assertEqual(split_list_field(" a ,b,, c ,"), ["a", "b", "c"])
        self.assertEqual(split_list_field(" , ,"), [])

    def test_quoted(self):
        self.assertEqual(split_list_field('a;b="x,y", c'), ['a;b="x,y"', "c"])
        self.assertEqual(split_list_field(r'"a\",b",c'), [r'"a\",b"', "c"])
        self.assertEqual(split_list_field('a"b"c,d'), ['a"b"c', "d"])

    def test_unterminated_quote(self):
        # Behaviour carried over from the regex implementation: text before a bad
        # quote that isn't followed by a comma is dropped.
        self.assertEqual(split_list_field('a"b,c'), ["b", "c"])
        self.assertEqual(split_list_field('"a,b'), ["a", "b"])
        self.assertEqual(split_list_field('a,"b'), ["a", "b"])
        self.assertEqual(split_list_field('a "b'), ["b"])
        self.assertEqual(split_list_field('a"'), [])
        self.assertEqual(split_list_field("a\\"), ["a\\"])

    def assert_fast(self, value):
        start = time.monotonic()
        split_list_field(value)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def test_unterminated_quote_is_linear(self):
        self.assert_fast("a" * SIZE + '"')
        self.assert_fast('"' + "a" * SIZE)
        self.assert_fast('"\\' * (SIZE // 2))
        self.assert_fast('"a' * (SIZE // 2))

    def test_empty_elements_are_linear(self):
        self.assert_fast(" ," * (SIZE // 2))
        self.assert_fast("," * SIZE)
        self.assert_fast(" " * SIZE)
        self.assert_fast(", " * (SIZE // 2) + "a")

    def test_many_elements_are_linear(self):
        self.assert_fast("a," * SIZE)
        self.assert_fast('"a,b",' * (SIZE // 6))


if __name__ == "__main__":
    unittest.main()
