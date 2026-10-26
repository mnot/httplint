"""
The helpers in test/slow.py: HTTPLINT_SLOW_TESTS parsing, and Mismatches reporting.
"""

import os
import unittest
from typing import Dict
from unittest import mock

from test.slow import ENV_VAR, CaseCrashed, Mismatches, size, slow_tests_enabled


class SlowTestsEnabledTest(unittest.TestCase):
    def enabled(self, value: str) -> bool:
        with mock.patch.dict(os.environ, {ENV_VAR: value}):
            return slow_tests_enabled()

    def test_on(self) -> None:
        for value in ["1", "true", "TRUE", "True", "yes", "Yes", " 1 "]:
            with self.subTest(value=value):
                self.assertTrue(self.enabled(value))

    def test_off(self) -> None:
        for value in ["", "0", "false", "False", "no", "NO", "off", "2", "enabled"]:
            with self.subTest(value=value):
                self.assertFalse(self.enabled(value))

    def test_unset(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop(ENV_VAR, None)
            self.assertFalse(slow_tests_enabled())
            self.assertEqual(size(3, 9), 3)

    def test_size(self) -> None:
        with mock.patch.dict(os.environ, {ENV_VAR: "1"}):
            self.assertEqual(size(3, 9), 9)
        with mock.patch.dict(os.environ, {ENV_VAR: "no"}):
            self.assertEqual(size(3, 9), 3)


class MismatchesTest(unittest.TestCase):
    def report(self, bad: Mismatches) -> str:
        with self.assertRaises(AssertionError) as caught:
            bad.assert_none(self)
        return str(caught.exception)

    def test_clean_run(self) -> None:
        bad = Mismatches()
        for value in range(5):
            with bad.case(value):
                self.assertEqual(value, value)
        bad.assert_none(self)
        self.assertEqual((bad.cases, bad.failed, bad.kept), (5, 0, []))

    def test_failure_names_input_and_both_results(self) -> None:
        bad = Mismatches()
        for value in ["ok", "bad", "fine"]:
            with bad.case(value):
                self.assertEqual(value, "expected" if value == "bad" else value)
        text = self.report(bad)
        self.assertIn("1 of 3 cases failed", text)
        self.assertIn("input 'bad'", text)
        self.assertIn("'bad' != 'expected'", text)
        self.assertNotIn("'fine'", text)

    def test_failure_names_the_failing_line(self) -> None:
        bad = Mismatches()
        with bad.case("first"):
            self.assertTrue(False)  # the first assertion
        with bad.case("second"):
            self.assertTrue(True)
            self.assertFalse(True)  # the second assertion
        text = self.report(bad)
        self.assertEqual(text.count("False is not true"), 1)
        self.assertIn("self.assertTrue(False)", text)
        self.assertIn("self.assertFalse(True)", text)
        self.assertIn("test_slow_helper.py:", text)

    def test_line_is_in_the_helper_not_in_unittest(self) -> None:
        def check(value: int) -> None:
            self.assertEqual(value, 0)  # inside a helper

        bad = Mismatches()
        with bad.case(7):
            check(7)
        self.assertIn("self.assertEqual(value, 0)", self.report(bad))

    def test_keeps_the_first_failures_and_counts_all(self) -> None:
        bad = Mismatches(limit=3)
        for value in range(10):
            with bad.case(value):
                self.fail("no")
        self.assertEqual((bad.cases, bad.failed, [k[0] for k in bad.kept]), (10, 10, [0, 1, 2]))
        text = self.report(bad)
        self.assertIn("10 of 10 cases failed; first 3", text)
        self.assertNotIn("input 3", text)

    def test_nesting_keeps_labels(self) -> None:
        bad = Mismatches()
        with bad.case("outer"):
            with bad.case("inner"):
                self.assertEqual(1, 2)
            self.assertEqual(3, 4)
        self.assertEqual(bad.cases, 2)
        self.assertEqual([k[0] for k in bad.kept], ["inner", "outer"])
        text = self.report(bad)
        self.assertIn("input 'inner'", text)
        self.assertIn("1 != 2", text)
        self.assertIn("input 'outer'", text)
        self.assertIn("3 != 4", text)

    def test_nesting_after_inner_block_labels_outer(self) -> None:
        bad = Mismatches()
        with bad.case("outer"):
            with bad.case("inner"):
                pass
            self.assertEqual(1, 2)
        self.assertEqual([k[0] for k in bad.kept], ["outer"])

    def test_crash_names_input_and_earlier_mismatches(self) -> None:
        bad = Mismatches()
        with bad.case("early"):
            self.assertEqual(1, 2)
        with self.assertRaises(CaseCrashed) as caught:
            for value in ["a", "b"]:
                with bad.case(value):
                    if value == "b":
                        raise ValueError("boom")
        text = str(caught.exception)
        self.assertIn("ValueError: boom", text)
        self.assertIn("input 'b'", text)
        self.assertIn("raise ValueError", text)
        self.assertIn("1 of 3 cases failed", text)
        self.assertIn("input 'early'", text)
        self.assertIn("1 != 2", text)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_crash_without_earlier_mismatches(self) -> None:
        bad = Mismatches()
        lookup: Dict[str, int] = {}
        with self.assertRaises(CaseCrashed) as caught:
            with bad.case(("x", 4)):
                lookup["missing"]  # pylint: disable=pointless-statement
        self.assertIn("KeyError", str(caught.exception))
        self.assertIn("input ('x', 4)", str(caught.exception))
        self.assertIn("No mismatches", str(caught.exception))

    def test_crash_in_a_nested_case_is_not_collected_as_a_failure(self) -> None:
        bad = Mismatches()
        with self.assertRaises(CaseCrashed) as caught:
            with bad.case("outer"):
                with bad.case("inner"):
                    raise RuntimeError("deep")
        self.assertIn("input 'inner'", str(caught.exception))
        self.assertEqual(bad.failed, 0)

    def test_skips_and_interrupts_pass_through(self) -> None:
        bad = Mismatches()
        with self.assertRaises(unittest.SkipTest):
            with bad.case(1):
                raise unittest.SkipTest("skip")
        with self.assertRaises(KeyboardInterrupt):
            with bad.case(2):
                raise KeyboardInterrupt()
        self.assertEqual(bad.failed, 0)


if __name__ == "__main__":
    unittest.main()
