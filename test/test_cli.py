import contextlib
import io
import sys
import unittest
from typing import List, Tuple
from unittest import mock

from httplint.cli import main

REQUEST = "GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n"
RESPONSE = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n"


def run_cli(args: List[str], stdin: str) -> Tuple[int, str, str]:
    "Run main() with the given argv and stdin; return (exit status, stdout, stderr)."
    out, err = io.StringIO(), io.StringIO()
    status = 0
    with (
        mock.patch.object(sys, "argv", ["httplint", *args]),
        mock.patch.object(sys, "stdin", io.StringIO(stdin)),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            main()
        except SystemExit as exc:
            status = exc.code if isinstance(exc.code, int) else 1
    return status, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def test_default_is_response(self) -> None:
        status, out, _ = run_cli([], RESPONSE)
        self.assertEqual(status, 0)
        self.assertIn("This response", out)

    def test_explicit_response(self) -> None:
        status, out, _ = run_cli(["-i", "response"], RESPONSE)
        self.assertEqual(status, 0)
        self.assertIn("This response", out)

    def test_request(self) -> None:
        status, out, err = run_cli(["-i", "request"], REQUEST)
        self.assertEqual(status, 0)
        self.assertEqual(err, "")
        self.assertIn("User-Agent header is missing", out)

    def test_unknown_mode(self) -> None:
        status, _, err = run_cli(["-i", "bogus"], REQUEST)
        self.assertEqual(status, 2)
        self.assertIn("invalid", err)

    def test_bad_request_line(self) -> None:
        status, out, err = run_cli(["-i", "request"], "BADLINE\r\nHost: a\r\n\r\n")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("httplint:", err)
        self.assertNotIn("Traceback", err)

    def test_bad_status_line(self) -> None:
        status, out, err = run_cli(["-i", "response"], "BADLINE\r\nHost: a\r\n\r\n")
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("start line", err)

    def test_bad_version(self) -> None:
        status, _, err = run_cli([], "HTTP/9 200 OK\r\n\r\n")
        self.assertEqual(status, 1)
        self.assertIn("version", err)


if __name__ == "__main__":
    unittest.main()
