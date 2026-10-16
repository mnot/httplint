"""
The CLI prints note summaries, which interpolate wire values; control
characters must not reach the terminal raw.
"""

import io
import unittest
from typing import Any
from unittest import mock
from argparse import Namespace
from contextlib import redirect_stdout

from httplint.cli.http_parser import HttpCliParser, modes, terminal_safe
from httplint.message import HttpResponseLinter
from httplint.note import Note, categories, levels


class PARENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Parent."
    _text = "Parent."


class CHILD(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Child '%(value)s'."
    _text = "Child."


def run_cli(mode: modes, data: bytes) -> str:
    out = io.StringIO()
    parser = HttpCliParser(Namespace(mode=mode))
    with redirect_stdout(out):
        parser.handle_input(data)
    return out.getvalue()


class TestCliTerminalSafety(unittest.TestCase):
    def test_response_escapes_controls(self) -> None:
        out = run_cli(
            modes.RESPONSE,
            b"HTTP/1.1 200 OK\r\nReferrer-Policy: \x1b[31mred\x07\r\nContent-Length: 0\r\n\r\n",
        )
        self.assertIn("* [", out)
        self.assertIn("\\x1b[31mred\\x07", out)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)

    def test_request_escapes_controls(self) -> None:
        out = run_cli(
            modes.REQUEST,
            b"GET / HTTP/1.1\r\nHost: example.com\r\nOrigin: \x1b]0;x\x07\r\n\r\n",
        )
        self.assertIn("\\x1b]0;x\\x07", out)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)

    def test_c1_and_soft_hyphen_end_to_end(self) -> None:
        out = run_cli(
            modes.RESPONSE,
            b"HTTP/1.1 200 OK\r\nReferrer-Policy: a\x9bb\xadc\r\nContent-Length: 0\r\n\r\n",
        )
        self.assertIn("a\\x9bb\\xadc", out)
        self.assertNotIn("\x9b", out)
        self.assertNotIn("\xad", out)

    def test_subnotes_escaped(self) -> None:
        def finish(self: HttpResponseLinter, *args: Any, **kwargs: Any) -> None:
            parent = self.notes.add("test", PARENT)
            parent.add_child(CHILD, value="\x1b[31m\u202e\xad")

        with mock.patch.object(HttpResponseLinter, "finish_content", finish):
            out = run_cli(modes.RESPONSE, b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        self.assertIn("  * [WARN] Child '\\x1b[31m\\u202e\\xad'.", out)
        for raw in ("\x1b", "\u202e", "\xad"):
            self.assertNotIn(raw, out)

    def test_helper(self) -> None:
        self.assertEqual(terminal_safe("a\x1bb\x7fc\x9bd\n"), "a\\x1bb\\x7fc\\x9bd\\x0a")
        self.assertEqual(terminal_safe("x\u202ey\u2028\xad"), "x\\u202ey\\u2028\\xad")
        self.assertEqual(
            terminal_safe("\u200b\u2060\ufeff\u061c\ud800\ue000\U000e0041\U0010ffff"),
            "\\u200b\\u2060\\ufeff\\u061c\\ud800\\ue000\\U000e0041\\U0010ffff",
        )
        self.assertEqual(
            terminal_safe("caf\u00e9 \u65e5\u672c \u00a0 \U0001f600 \\x1b"),
            "caf\u00e9 \u65e5\u672c \u00a0 \U0001f600 \\x1b",
        )
