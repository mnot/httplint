"""
split_params must split a parameter list into name=value parameters, in linear time.

It replaces a split_string() call whose regex backtracked quadratically.
"""

import time
import unittest

from httplint.field.utils import split_params

# Generous: linear inputs take well under a second; the quadratic ones took seconds.
TIME_LIMIT = 2.0
SIZE = 64_000


class SplitParamsTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(split_params(""), [])
        self.assertEqual(split_params("a=b"), ["a=b"])
        self.assertEqual(split_params("a=b; c=d ;e=f"), ["a=b", "c=d", "e=f"])
        self.assertEqual(split_params(";a=b;;"), ["a=b"])

    def test_quoted(self):
        self.assertEqual(split_params('a="x;y"; b=c'), ['a="x;y"', "b=c"])
        self.assertEqual(split_params(r'a="x\";y";b=c'), [r'a="x\";y"', "b=c"])

    def test_malformed_is_skipped(self):
        # Pinned to match the regex this replaced: text that isn't a parameter followed
        # by a separator is dropped without comment.
        self.assertEqual(split_params("a=b c=d"), ["c=d"])
        self.assertEqual(split_params("a;b=c"), ["b=c"])
        self.assertEqual(split_params('a="b;c=d'), ["c=d"])
        self.assertEqual(split_params("a=;b=c"), ["b=c"])

    def test_whitespace(self):
        self.assertEqual(split_params("a=b ;\x0bc=d\n"), ["a=b", "c=d"])

    def assert_fast(self, value):
        start = time.monotonic()
        split_params(value)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def test_no_equals_is_linear(self):
        self.assert_fast("a" * SIZE)
        self.assert_fast(";" + "a" * SIZE)

    def test_unterminated_quote_is_linear(self):
        self.assert_fast('a="' + "a" * SIZE)
        self.assert_fast('a="' + "a=" * (SIZE // 2))
        self.assert_fast('a="\\"' * (SIZE // 5))

    def test_trailing_junk_is_linear(self):
        self.assert_fast("a=b" + "c" * SIZE + " x")
        self.assert_fast("a=b" + " " * SIZE + "x")
        self.assert_fast("a=b " * (SIZE // 4))

    def test_many_parameters_are_linear(self):
        self.assert_fast("a=b;" * (SIZE // 4))
        self.assert_fast('a="b;c";' * (SIZE // 8))
        self.assert_fast(";" * SIZE)
        self.assert_fast(" " * SIZE)


if __name__ == "__main__":
    unittest.main()
