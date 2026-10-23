"""
split_list_field must split on commas outside quoted-strings, in linear time.

It used to be a regex that backtracked quadratically on some inputs.
"""

import itertools
import time
import unittest

from httplint.field.utils import split_list_field

# Generous: linear inputs take well under a second; the quadratic ones took minutes.
TIME_LIMIT = 5.0
SIZE = 100_000
# For the angle-target cache: an uncached search takes 6-12 s at 400,000 repeats on a
# laptop; the real thing takes 0.2-0.4 s.
ANGLE_SIZE = 500_000
ANGLE_LIMIT = 3.0


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


class AngleTargetSplitTest(unittest.TestCase):
    "angle_targets=True keeps a leading <...> whole, for Link."

    def split(self, value):
        return split_list_field(value, angle_targets=True)

    def test_comma_in_target(self):
        self.assertEqual(self.split("<http://a/b,c>; rel=next"), ["<http://a/b,c>; rel=next"])
        self.assertEqual(self.split("<a,b>, <c,d>"), ["<a,b>", "<c,d>"])
        self.assertEqual(self.split("<a,,b>"), ["<a,,b>"])
        self.assertEqual(self.split(" \t<a,b>; rel=x , </c>"), ["<a,b>; rel=x", "</c>"])

    def test_default_is_unchanged(self):
        self.assertEqual(split_list_field("<a,b>; rel=x"), ["<a", "b>; rel=x"])

    def test_quotes_after_the_target(self):
        self.assertEqual(self.split('<a,b>; t="x,y", <c>'), ['<a,b>; t="x,y"', "<c>"])
        self.assertEqual(self.split('<a>; t="x>,<y", <c>'), ['<a>; t="x>,<y"', "<c>"])

    def test_quote_inside_target_does_not_swallow_commas(self):
        self.assertEqual(self.split('<a"b>, <c"d>'), ['<a"b>', '<c"d>'])

    def test_not_a_bracketed_target(self):
        # No ">" at all, or another "<" first: ordinary characters, split as usual.
        self.assertEqual(self.split("<a,b"), ["<a", "b"])
        self.assertEqual(self.split("<a, <b>"), ["<a", "<b>"])
        self.assertEqual(self.split("<a,b, <c>, <d"), ["<a", "b", "<c>", "<d"])
        # Only at the start of an item.
        self.assertEqual(self.split("x<a,b>"), ["x<a", "b>"])
        self.assertEqual(self.split('t="<", a,b>'), ['t="<"', "a", "b>"])

    def test_same_as_default_without_angle_brackets(self):
        alphabet = ['"', "\\", ",", " ", "a", ";", "="]
        for length in range(7):
            for chars in itertools.product(alphabet, repeat=length):
                value = "".join(chars)
                self.assertEqual(self.split(value), split_list_field(value), value)

    def test_every_split_is_a_split_of_the_default(self):
        "Joining pieces never loses text: only the commas inside a target change."
        alphabet = ["<", ">", ",", "a", '"']
        for length in range(8):
            for chars in itertools.product(alphabet, repeat=length):
                value = "".join(chars)
                got = self.split(value)
                self.assertEqual(
                    [c for c in "".join(got) if c != ","],
                    [c for c in "".join(split_list_field(value)) if c != ","],
                    value,
                )

    def assert_fast(self, value):
        start = time.monotonic()
        self.split(value)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def assert_fast_for(self, value, limit):
        start = time.monotonic()
        self.split(value)
        self.assertLess(time.monotonic() - start, limit)

    def test_unclosed_brackets_are_linear(self):
        # Without remembering that there is no ">", each "<" would search to the end:
        # quadratic, and several seconds at this size (the real thing takes ~0.3 s).
        self.assert_fast_for("<a," * ANGLE_SIZE, ANGLE_LIMIT)
        self.assert_fast_for("< a, " * (ANGLE_SIZE // 2), ANGLE_LIMIT)

    def test_distant_closing_bracket_is_linear(self):
        # Without reusing the ">" already found, each "<" would search to the far end.
        self.assert_fast_for("<a," * ANGLE_SIZE + ">", ANGLE_LIMIT)
        self.assert_fast_for("< a, " * (ANGLE_SIZE // 2) + ">", ANGLE_LIMIT)

    def test_other_shapes_are_linear(self):
        "Guards: these were not slow in any version tried."
        self.assert_fast("<a>," * (SIZE // 4))
        self.assert_fast("<" + "a," * SIZE + ">")
        self.assert_fast(("<" + "a" * 10 + ">, ") * (SIZE // 14))
        self.assert_fast('<a>"' * (SIZE // 4))
        self.assert_fast("<>" * SIZE)


if __name__ == "__main__":
    unittest.main()
