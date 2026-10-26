"""
split_list_field must split on commas outside quoted-strings, in linear time.

It used to be a regex that backtracked quadratically on some inputs.
"""

import itertools
import time
import unittest

from httplint.field.utils import _QDTEXT, _QUOTED_PAIR_CHAR, split_list_field
from test.slow import Mismatches, size

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
        for value in ['a;b="x,y", c', 'a"b,c', " a ,b,, c ,", r'"a\",b",c', "", " , ,"]:
            self.assertEqual(self.split(value), split_list_field(value), value)

    def test_unmatched_is_linear(self):
        # A naive scan from each "(" to the end is quadratic.
        self.assertLess(self.timed("(" * SIZE), TIME_LIMIT)
        self.assertLess(self.timed("(a," * (SIZE // 3)), TIME_LIMIT)
        self.assertLess(self.timed(")" * SIZE), TIME_LIMIT)
        self.assertLess(self.timed("(" * (SIZE // 2) + ")" * (SIZE // 2)), TIME_LIMIT)
        self.assertLess(self.timed("(,)," * (SIZE // 4)), TIME_LIMIT)

    def test_escaped_parens_are_linear(self):
        # Quadratic when each unmatched "(" was matched by rescanning to the end; the escaped
        # ones in particular were never remembered.
        for unit in ["\\(", "(\\(", "\\)", "\\\\", "(\\", "\\()", "(\\)"]:
            for size in (SIZE // len(unit), 32_000 // len(unit)):
                self.assertLess(self.timed(unit * size), 1.0, unit)
        self.assertLess(self.timed("1.1 a " + "\\(" * 4000), 1.0)

    def timed(self, value):
        start = time.monotonic()
        self.split(value)
        return time.monotonic() - start


def reference_split(value, comments):
    "A slow, direct implementation of the splitting rules, to compare against."

    def quote_close(start):
        "Index just after the closing quote of the quoted-string opening at `start`, or -1."
        idx = start + 1
        while idx < len(value):
            char = value[idx]
            if char == '"':
                return idx + 1
            if char in _QDTEXT:
                idx += 1
            elif char == "\\" and idx + 1 < len(value) and value[idx + 1] in _QUOTED_PAIR_CHAR:
                idx += 2
            else:
                return -1
        return -1

    def comment_close(start):
        "Index just after the ')' matching the '(' at `start`, or -1."
        depth = 1
        idx = start + 1
        while idx < len(value):
            char = value[idx]
            if char == "\\" and idx + 1 < len(value) and value[idx + 1] in _QUOTED_PAIR_CHAR:
                idx += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return idx + 1
            idx += 1
        return -1

    items = []
    item_start = 0
    idx = 0
    while idx < len(value):
        char = value[idx]
        jump = -1
        if char == ",":
            items.append(value[item_start:idx].strip())
            item_start = idx + 1
        elif char == '"':
            jump = quote_close(idx)
        elif char == "(" and comments:
            jump = comment_close(idx)
        idx = jump if jump >= 0 else idx + 1
    items.append(value[item_start:].strip())
    return [item for item in items if item]


class SplitListFieldDifferentialTest(unittest.TestCase):
    "The linear splitter agrees with the direct one on every short string."

    ALPHABET = 'a()\\", '

    def test_exhaustive(self):
        bad = Mismatches()
        for length in range(size(7, 8)):
            for chars in itertools.product(self.ALPHABET, repeat=length):
                value = "".join(chars)
                for comments in (False, True):
                    with bad.case((value, comments)):
                        self.assertEqual(
                            split_list_field(value, comments=comments),
                            reference_split(value, comments),
                            (value, comments),
                        )
        bad.assert_none(self)
        self.assertGreater(bad.cases, size(100_000, 1_000_000))


if __name__ == "__main__":
    unittest.main()
