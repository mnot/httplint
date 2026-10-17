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

    def test_quoted_character_classes(self):
        # obs-text and HTAB are allowed inside a quoted-string; controls and DEL aren't,
        # nor is a backslash before one. The quote then doesn't open a quoted-string, and the
        # item is kept (for the syntax check to report) rather than dropped.
        self.assertEqual(split_list_field('"\xe9",c'), ['"\xe9"', "c"])
        self.assertEqual(split_list_field('"a\tb",c'), ['"a\tb"', "c"])
        self.assertEqual(split_list_field('"a\x00b",c'), ['"a\x00b"', "c"])
        self.assertEqual(split_list_field('"a\x7fb",c'), ['"a\x7fb"', "c"])
        self.assertEqual(split_list_field('"\\\x00",c'), ['"\\\x00"', "c"])

    def test_whitespace(self):
        # Whitespace as str.strip() and the regex \s see it, not only SP and HTAB.
        self.assertEqual(split_list_field("\x0ba\x0c,\u2003b\u2003"), ["a", "b"])

    def test_unterminated_quote(self):
        # A quote that doesn't open a valid quoted-string is an ordinary character of its
        # item, so the malformed item reaches the field's syntax check rather than being
        # dropped.
        self.assertEqual(split_list_field('a"b,c'), ['a"b', "c"])
        self.assertEqual(split_list_field('"a,b'), ['"a', "b"])
        self.assertEqual(split_list_field('a,"b'), ["a", '"b'])
        self.assertEqual(split_list_field('a "b'), ['a "b'])
        self.assertEqual(split_list_field('a"'), ['a"'])
        self.assertEqual(split_list_field('max-age=60"'), ['max-age=60"'])
        self.assertEqual(
            split_list_field('no-store, max-age=60"x'), ["no-store", 'max-age=60"x']
        )
        self.assertEqual(split_list_field("a\\"), ["a\\"])

    def assert_fast(self, value):
        start = time.monotonic()
        split_list_field(value)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def test_unterminated_quote_is_linear(self):
        # Reproducer: quadratic on the old regex.
        self.assert_fast("a" * SIZE + '"')
        # Regression guards: these were not slow on the old regex.
        self.assert_fast('"' + "a" * SIZE)
        self.assert_fast('"\\' * (SIZE // 2))
        self.assert_fast('"a' * (SIZE // 2))

    def test_empty_elements_are_linear(self):
        # Reproducer: quadratic on the old regex.
        self.assert_fast(" ," * (SIZE // 2))
        # Regression guards.
        self.assert_fast("," * SIZE)
        self.assert_fast(" " * SIZE)
        self.assert_fast(", " * (SIZE // 2) + "a")

    def test_many_elements_are_linear(self):
        # Regression guards.
        self.assert_fast("a," * SIZE)
        self.assert_fast('"a,b",' * (SIZE // 6))


if __name__ == "__main__":
    unittest.main()
