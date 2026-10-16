import gzip
import os
import subprocess
import sys
import unittest
from typing import Dict


def run_cli(message: bytes, env_extra: Dict[str, str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", "from httplint.cli import main; main()"],
        input=message,
        capture_output=True,
        env=env,
        check=False,
    )


class TestCliBinaryInput(unittest.TestCase):
    "The CLI must read stdin as bytes, regardless of locale."

    body = gzip.compress(b"hello world" * 20)
    message = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Encoding: gzip\r\n"
        b"Content-Length: %d\r\n\r\n" % len(body)
    ) + body

    def check(self, env_extra: Dict[str, str]) -> None:
        result = run_cli(self.message, env_extra)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        out = result.stdout.decode()
        self.assertNotIn("GZIP header wasn't valid", out)
        self.assertIn("The Content-Length header is correct", out)

    def test_utf8_locale(self) -> None:
        self.check({"LC_ALL": "en_US.UTF-8", "PYTHONUTF8": "0"})

    def test_c_locale(self) -> None:
        self.check(
            {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
        )

    def test_utf8_mode(self) -> None:
        self.check({"PYTHONUTF8": "1"})


if __name__ == "__main__":
    unittest.main()
