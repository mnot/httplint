"""
Differential test of split_list_field() against the regex it replaced.

Every short string over a nasty alphabet (quotes, backslash, comma, whitespace,
control and non-Latin-1 characters) plus random longer ones is checked. Where every
quote opens a valid quoted-string, the output must be identical to the regex's. Where
one doesn't, the regex dropped text; the function must instead keep every character
(bar commas and whitespace), and every item the regex produced must survive inside
one of its items. Keep this in step with the function if its behaviour is deliberately
changed.

Usage: PYTHONPATH=. .venv/bin/python tools/diff_split_list_field.py [random-count]
"""

import itertools
import random
import re
import sys
from typing import List

from httplint.field.utils import RE_FLAGS, split_list_field
from httplint.syntax import rfc9110

ALPHABET = ["a", " ", "\t", ",", '"', "\\", "\n", "\x00", "\x7f", "\xe9", chr(0x100), chr(0x2003)]
EXHAUSTIVE_LENGTH = 6


def old_split_list_field(field_value: str) -> List[str]:
    "The original implementation, verbatim apart from formatting."
    return [
        stripped
        for stripped in (
            f.strip()
            for f in re.findall(
                r'((?:[^",]|%s)+)(?=%s|\s*$)' % (rfc9110.quoted_string, r"(?:\s*(?:,\s*)+)"),
                field_value,
                RE_FLAGS,
            )
        )
        if stripped
    ]


WELL_FORMED = re.compile(rf'(?:[^"]|{rfc9110.quoted_string})*', RE_FLAGS)
SKIPPED = re.compile(r"[\s,]+")


def check(value: str) -> bool:
    old = old_split_list_field(value)
    new = split_list_field(value)
    if WELL_FORMED.fullmatch(value):
        return old == new
    kept = SKIPPED.sub("", "".join(new)) == SKIPPED.sub("", value)
    return kept and all(any(item in n for n in new) for item in old)


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
        if not check(value):
            differences += 1
            if differences <= 10:
                print("DIFFERENT:", repr(value))
    print(f"{checked} inputs, {differences} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
