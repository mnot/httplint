"""
Differential test of split_params() against the split_string() call it replaced.

Every short string over a nasty alphabet (quotes, backslash, semicolon, equals,
whitespace, control and non-Latin-1 characters) plus random longer ones must give
identical output. Keep this in step with the function if its behaviour is deliberately
changed.

Usage: PYTHONPATH=. .venv/bin/python tools/diff_split_params.py [random-count]
"""

import itertools
import random
import sys

from httplint.field.utils import split_params, split_string
from httplint.syntax import rfc9110

ALPHABET = ["a", "=", ";", " ", "\t", '"', "\\", "\n", "'", "\x00", "\xe9", chr(0x100), chr(0x2003)]
EXHAUSTIVE_LENGTH = 6


def old_split_params(instr: str) -> list[str]:
    "The original call from parse_params."
    return split_string(instr, rfc9110.parameter, r"\s*;\s*")


def candidates(random_count: int):
    for length in range(EXHAUSTIVE_LENGTH + 1):
        for chars in itertools.product(ALPHABET, repeat=length):
            yield "".join(chars)
    rnd = random.Random(1)
    for _ in range(random_count):
        yield "".join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 300)))


def main() -> int:
    random_count = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    checked = differences = 0
    for value in candidates(random_count):
        checked += 1
        if old_split_params(value) != split_params(value):
            differences += 1
            if differences <= 10:
                print("DIFFERENT:", repr(value))
    print(f"{checked} inputs, {differences} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
