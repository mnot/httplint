"""
HTTP-date parsing and the notes about bad or obsolete dates.
"""

import calendar
import re
import time
from email.utils import parsedate as lib_parsedate
from typing import Optional, Tuple

from httplint.field.common import RE_FLAGS
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


def parse_http_date(
    value: str,
    add_note: AddNoteMethodType,
    category: Optional[categories] = None,
    now: Optional[float] = None,
) -> int:
    """
    Parse a HTTP date. Raises ValueError if it's bad.

    ``now`` is the reference time (seconds since the epoch) for resolving the
    two-digit year of an rfc850-date, as RFC 9110 Section 5.6.7 requires; it defaults
    to the current time. Callers with a message should pass its ``start_time`` so that
    linting a recorded exchange is repeatable.
    """
    if not re.match(rf"^{rfc9110.HTTP_date}$", value, RE_FLAGS):
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    if re.match(rf"^{rfc9110.obs_date}$", value, RE_FLAGS):
        add_note(DATE_OBSOLETE, category=category)
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    # IMF-fixdate and asctime-date have four-digit years, which parsedate would
    # otherwise treat as two-digit ones ("0000" -> 2000); rfc850-date's own two-digit
    # years are resolved below, not by parsedate's fixed pivot.
    year_match = re.search(r"(?<!\d)\d{4}(?!\d)", value)
    year, month, day, hour, minute, second = date_tuple[:6]
    if year_match:
        year = int(year_match.group())
    else:
        year = _resolve_two_digit_year(
            year % 100, (month, day, hour, minute, second), _time_or_now(now)
        )
    # Out-of-range fields would be silently normalised by timegm.
    if year < 1 or not 1 <= month <= 12 or day < 1 or day > calendar.monthrange(year, month)[1]:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    # A second of 60 is a leap second.
    if hour > 23 or minute > 59 or second > 60:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    return calendar.timegm((year, month, day, hour, minute, second))


class BAD_DATE_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header's value isn't a valid date."
    _text = """\
HTTP dates have specific syntax, and sending an invalid date can cause a number of problems,
especially with caching. Common problems include sending "1 May" instead of "01 May" (the month
is a fixed-width field), and sending a date in a timezone other than GMT.

See [the HTTP specification](https://www.rfc-editor.org/rfc/rfc9110.html#name-date-time-formats) for more
information."""


class DATE_OBSOLETE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header's value uses an obsolete format."
    _text = """\
HTTP has a number of defined date formats for historical reasons. This header is using an old
format that are now obsolete. See [the
specification](https://www.rfc-editor.org/rfc/rfc9110.html#name-obsolete-date-formats) for more information.
"""


def _time_or_now(now: Optional[float]) -> time.struct_time:
    "The reference time as UTC fields; the current time if ``now`` is missing or unusable."
    if now is not None:
        try:
            return time.gmtime(now)
        except (OverflowError, OSError, ValueError):
            pass
    return time.gmtime()


def _resolve_two_digit_year(
    two_digits: int, rest: Tuple[int, int, int, int, int], now: time.struct_time
) -> int:
    """
    The year for a two-digit rfc850-date year, per RFC 9110 Section 5.6.7: a timestamp
    that appears to be more than 50 years in the future is the most recent past year
    with the same last two digits.

    ``rest`` is (month, day, hour, minute, second). Comparing those against ``now``
    rather than building a date 50 years on keeps 29 February from being a special case.
    """
    limit_year = now.tm_year + 50
    year = limit_year - (limit_year - two_digits) % 100
    now_rest = (now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
    if year == limit_year and rest > now_rest:
        year -= 100
    return year
