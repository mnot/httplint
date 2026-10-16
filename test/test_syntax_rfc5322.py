import re
import time
import unittest

from httplint.message import HttpRequestLinter
from httplint.syntax import rfc5322

FLAGS = re.VERBOSE | re.IGNORECASE
MAILBOX = re.compile(rf"^\s*(?:{rfc5322.mailbox})\s*$", FLAGS)

N = 5000
TIME_LIMIT = 1.0  # seconds; the exponential grammar needed minutes at 30 characters

ACCEPTED = [
    "webmaster@example.org",
    "webmaster@example.org (Web Master)",
    "<w@example.org>",
    "Bob <w@example.org>",
    "Bob Smith <w@example.org>",
    '"Bob, Jr." <w@example.org>',
    '"b o"@example.org',
    "w@[1.2.3.4]",
    "a.b.c@d.e.f",
    "(c) Bob (d) <w@example.org> (e)",
    "Bob\r\n Smith <w@example.org>",
    "obs_phrase <w@example.org>",
]

REJECTED = [
    "",
    "aaaa",
    "Bob <w@example.org",
    "Bob w@example.org>",
    "w@",
    "@example.org",
    "Bob <>",
    "Bob\r\nSmith <w@example.org>",
    "(unclosed w@example.org",
]

ADVERSARIAL = {
    "atoms": "a" * N,
    "spaced atoms": "a " * (N // 2),
    "atoms then junk": "a" * N + "\x00",
    "quoted string": '"' + "a" * N,
    "quoted pairs": '"' + "\\a" * (N // 2),
    "spaces in quotes": '"' + " " * N,
    "comments": "(c) " * (N // 4) + "\x00",
    "open comment": "(" * N,
    "comment content": "(" + "a" * N,
    "whitespace": " " * N + "\x00",
    "address then whitespace": "w@x.org" + " " * N + "\x00",
    "folds": "a" + "\r\n " * (N // 3) + "\x00",
    "phrase then angle": "a " * (N // 2) + "<",
    "local part": "a" * N + "@",
    "domain": "a@" + "a" * N + "\x00",
    "domain literal": "a@[" + "a " * (N // 2),
    "dotted": "a." * (N // 2),
}


class TestMailbox(unittest.TestCase):
    def test_accepted(self):
        for value in ACCEPTED:
            self.assertTrue(MAILBOX.match(value), repr(value))

    def test_rejected(self):
        for value in REJECTED:
            self.assertFalse(MAILBOX.match(value), repr(value))

    def test_adversarial_input_is_bounded(self):
        for name, value in ADVERSARIAL.items():
            start = time.perf_counter()
            MAILBOX.match(value)
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{name}: {elapsed:.2f}s")

    def test_from_header_is_bounded(self):
        for value in (b"a" * N + b"\x00", b" " * N + b"\x00", b"w@x.org" + b" " * N + b"\x00"):
            linter = HttpRequestLinter()
            linter.process_request_topline(b"GET", b"http://a/", b"1.1")
            start = time.perf_counter()
            linter.process_headers([(b"From", value)])
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{value[:8]!r}: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
