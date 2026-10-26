#!/usr/bin/env python3

"""
Note summaries are plain text (only a note's text is Markdown), so they must not use backticks.
"""

import unittest

from httplint.note import Note
from test.utils import checkSubClasses


class NoteSummaryTest(unittest.TestCase):
    def test_no_backticks_in_summaries(self) -> None:
        offenders = []

        def check(note_cls: type[Note]) -> int:
            if "`" in str(note_cls.__dict__.get("_summary", "")):
                offenders.append(f"{note_cls.__module__}.{note_cls.__name__}")
                return 1
            return 0

        count, _ = checkSubClasses(
            Note, ["httplint", "httplint/field", "httplint/field/parsers"], check
        )
        self.assertGreater(count, 0)
        self.assertEqual(offenders, [], "plain-text summary contains a backtick")


if __name__ == "__main__":
    unittest.main()
