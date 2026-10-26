"""
Depth control for the exhaustive and differential tests.

A test that enumerates every string over an alphabet, or compares an old and a new grammar over
thousands of inputs, costs more with each added character. By default those tests run a capped
enumeration: the same alphabet and checks, shorter strings. Setting HTTPLINT_SLOW_TESTS=1 runs the
full enumeration, which you should do whenever a grammar changes:

    HTTPLINT_SLOW_TESTS=1 make test_syntax

Import it as `from test.slow import ...`; that works under pytest, under `make test_%` (which runs
each file as a script with PYTHONPATH=.) and under test/coverage.py.
"""

import os
import unittest
from types import TracebackType
from typing import Any, List, Optional, Tuple, Type

ENV_VAR = "HTTPLINT_SLOW_TESTS"


def slow_tests_enabled() -> bool:
    "True when the full (slow) enumerations are wanted."
    return os.environ.get(ENV_VAR, "") not in ("", "0")


def size(capped: int, full: int) -> int:
    "Pick a depth (string length, count, ...) for this run: `full` when slow tests are enabled."
    return full if slow_tests_enabled() else capped


class Mismatches:
    """
    Collects failures from a long loop and reports them once, instead of one subTest per case.

        bad = Mismatches()
        for value in strings(alphabet, size(4, 6)):
            with bad.case(value):
                self.assertEqual(now(value), reference(value))
        bad.assert_none(self)

    Only AssertionError is collected; any other exception stops the test as usual. The first
    `limit` failures are kept, each with its input and the assertion's message (which has both
    results); `cases` counts everything examined, so a test can check that it ran something.
    Not re-entrant: one `case()` at a time.
    """

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self.cases = 0
        self.failed = 0
        self.kept: List[Tuple[Any, str]] = []
        self._label: Any = None

    def case(self, label: Any) -> "Mismatches":
        self.cases += 1
        self._label = label
        return self

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        if exc_type is None or not issubclass(exc_type, AssertionError):
            return False
        self.failed += 1
        if len(self.kept) < self.limit:
            self.kept.append((self._label, str(exc)))
        return True

    def assert_none(self, test: unittest.TestCase) -> None:
        if not self.failed:
            return
        lines = [f"{self.failed} of {self.cases} cases failed; first {len(self.kept)}:"]
        for label, message in self.kept:
            lines.append(f"  input {label!r}: {message}")
        test.fail("\n".join(lines))
