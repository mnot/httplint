"""
The CLI prints note summaries, which interpolate wire values; control
characters must not reach the terminal raw.
"""

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout

from httplint.cli.http_parser import HttpCliParser, modes, terminal_safe


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

    def test_helper(self) -> None:
        self.assertEqual(terminal_safe("a\x1bb\x7fc\x9bd\n"), "a\\x1bb\\x7fc\\x9bd\\x0a")
        self.assertEqual(terminal_safe("x‮y "), "x\\u202ey\\u2028")
        self.assertEqual(terminal_safe("café 日本  "), "café 日本  ")
