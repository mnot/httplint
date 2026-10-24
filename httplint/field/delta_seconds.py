"""
Non-negative integer field values (delta-seconds and similar).
"""

from typing import Any, Optional, Type

from httplint.note import Note
from httplint.types import AddNoteMethodType


def parse_digits(value: str, max_digits: int = 20) -> Optional[int]:
    """
    Parse `value` as DIGIT+ (ASCII only; no sign, underscore or whitespace), or return None if it
    isn't, or has more than `max_digits` significant digits (leading zeros don't count).

    This keeps int()'s leniency and its 4300-digit limit away from wire values.
    """
    if value.isascii() and value.isdigit():
        digits = value.lstrip("0") or "0"
        if len(digits) <= max_digits:
            return int(digits)
    return None


def parse_delta_seconds(
    value: str,
    add_note: AddNoteMethodType,
    bad_note: Type[Note],
    max_digits: int = 20,
    **note_vars: Any,
) -> Optional[int]:
    """
    Parse `value` with parse_digits(), as used for delta-seconds and similar values.

    On failure, add `bad_note` (with `note_vars`) and return None. Range checks stay with the
    caller.
    """
    result = parse_digits(value, max_digits)
    if result is None:
        add_note(bad_note, **note_vars)
    return result


def is_negative_integer(value: str) -> bool:
    "True if `value` is '-' followed by ASCII DIGIT+; for choosing a more specific note."
    magnitude = value[1:]
    return value.startswith("-") and magnitude.isascii() and magnitude.isdigit()
