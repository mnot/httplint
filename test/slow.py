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
import traceback
import unittest
from types import TracebackType
from typing import Any, List, Optional, Tuple

ENV_VAR = "HTTPLINT_SLOW_TESTS"
_TRUE = ("1", "true", "yes")
_UNITTEST_DIR = os.path.dirname(unittest.__file__)


def slow_tests_enabled() -> bool:
    "True when the full (slow) enumerations are wanted: HTTPLINT_SLOW_TESTS is 1, true or yes."
    return os.environ.get(ENV_VAR, "").strip().lower() in _TRUE


def size(capped: int, full: int) -> int:
    "Pick a depth (string length, count, ...) for this run: `full` when slow tests are enabled."
    return full if slow_tests_enabled() else capped


class CaseCrashed(Exception):
    "The body of a Mismatches.case() raised something other than an AssertionError."


def _failing_line(tb: Optional[TracebackType]) -> str:
    "The file:line and source of the innermost frame that isn't inside unittest."
    frames = [
        frame for frame in traceback.extract_tb(tb) if not frame.filename.startswith(_UNITTEST_DIR)
    ]
    if not frames:
        return "?"
    frame = frames[-1]
    return f"{os.path.basename(frame.filename)}:{frame.lineno}: {frame.line}"


class _Case:
    "One pass through a Mismatches.case() block; it holds the label, so cases can nest."

    __slots__ = ("owner", "label")

    def __init__(self, owner: "Mismatches", label: Any) -> None:
        self.owner = owner
        self.label = label

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        if exc_type is None or exc is None:
            return False
        if issubclass(exc_type, AssertionError):
            self.owner.record(self.label, str(exc), tb)
            return True
        if not issubclass(exc_type, Exception) or issubclass(
            exc_type, (unittest.SkipTest, CaseCrashed)
        ):
            return False  # a skip, an interrupt, or a crash already reported by an inner case
        raise CaseCrashed(
            f"{exc_type.__name__}: {exc} while checking input {self.label!r} "
            f"({_failing_line(tb)})\n{self.owner.report()}"
        ) from exc


class Mismatches:
    """
    Collects failures from a long loop and reports them once, instead of one subTest per case.

        bad = Mismatches()
        for value in strings(alphabet, size(4, 6)):
            with bad.case(value):
                self.assertEqual(now(value), reference(value))
        bad.assert_none(self)

    An AssertionError in the block is collected. The first `limit` are kept, each with its input,
    the line that failed and the assertion's message (which has both results); `cases` counts
    everything examined, so a test can check that it ran something. Any other exception ends the
    test at once, as CaseCrashed: its message names the input and lists the mismatches collected
    so far (the original exception is its __cause__). Skips and interrupts pass through. Cases
    can nest.
    """

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self.cases = 0
        self.failed = 0
        self.kept: List[Tuple[Any, str, str]] = []

    def case(self, label: Any) -> _Case:
        self.cases += 1
        return _Case(self, label)

    def record(self, label: Any, message: str, tb: Optional[TracebackType]) -> None:
        self.failed += 1
        if len(self.kept) < self.limit:
            self.kept.append((label, _failing_line(tb), message))

    def report(self) -> str:
        "What has failed so far, one line per kept failure."
        if not self.failed:
            return "No mismatches collected before this."
        lines = [f"{self.failed} of {self.cases} cases failed; first {len(self.kept)}:"]
        for label, where, message in self.kept:
            lines.append(f"  input {label!r} [{where}]: {message}")
        return "\n".join(lines)

    def assert_none(self, test: unittest.TestCase) -> None:
        if self.failed:
            test.fail(self.report())
