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


class SplitListFieldCommentsTest(unittest.TestCase):
    "Comma splitting with `comments=True`, as Via uses it."

    @staticmethod
    def split(value):
        return split_list_field(value, comments=True)

    def test_comment(self):
        self.assertEqual(self.split("1.1 a (x, y), 1.1 b"), ["1.1 a (x, y)", "1.1 b"])
        self.assertEqual(self.split("(,),(,)"), ["(,)", "(,)"])

    def test_default_ignores_comments(self):
        self.assertEqual(split_list_field("1.1 a (x, y)"), ["1.1 a (x", "y)"])

    def test_nested(self):
        self.assertEqual(self.split("a (b (c, d), e), f"), ["a (b (c, d), e)", "f"])
        # Deeper than the syntax rule unrolls: still one item, so one syntax note.
        deep = "a " + "(" * 6 + "x, y" + ")" * 6
        self.assertEqual(self.split(deep + ", b"), [deep, "b"])

    def test_quoted_pair(self):
        self.assertEqual(self.split(r"a (b \), c), d"), [r"a (b \), c)", "d"])
        self.assertEqual(self.split(r"a (b \\), c"), [r"a (b \\)", "c"])

    def test_quote_and_comment(self):
        # A parenthesis in a quoted-string isn't a comment; a quote in a comment isn't a quote.
        self.assertEqual(self.split('a="(", b, c=")"'), ['a="("', "b", 'c=")"'])
        self.assertEqual(self.split('a (say "hi, there"), b'), ['a (say "hi, there")', "b"])
        self.assertEqual(self.split('a (say "hi), b'), ['a (say "hi)', "b"])

    def test_unmatched(self):
        # An unmatched "(" is an ordinary character, so the malformed item reaches the
        # syntax check and the list still splits.
        self.assertEqual(self.split("a (b, c"), ["a (b", "c"])
        self.assertEqual(self.split("a b), c"), ["a b)", "c"])
        self.assertEqual(self.split("((a, b), c"), ["((a, b)", "c"])
        self.assertEqual(self.split("a\\"), ["a\\"])

    def test_same_as_default_without_parens(self):
        for value in ['a;b="x,y", c', 'a"b,c', ' a ,b,, c ,', r'"a\",b",c', "", " , ,"]:
            self.assertEqual(self.split(value), split_list_field(value), value)

    def test_unmatched_is_linear(self):
        # A naive scan from each "(" to the end is quadratic.
        self.assertLess(self.timed("(" * SIZE), TIME_LIMIT)
        self.assertLess(self.timed("(a," * (SIZE // 3)), TIME_LIMIT)
        self.assertLess(self.timed(")" * SIZE), TIME_LIMIT)
        self.assertLess(self.timed("(" * (SIZE // 2) + ")" * (SIZE // 2)), TIME_LIMIT)
        self.assertLess(self.timed("(,)," * (SIZE // 4)), TIME_LIMIT)

    def timed(self, value):
        start = time.monotonic()
        self.split(value)
        return time.monotonic() - start


if __name__ == "__main__":
    unittest.main()
