"""
parse_http_date must reject dates that don't exist rather than normalising them, and
must not apply a two-digit-year pivot to four-digit years.
"""

import calendar
import time
import unittest
from typing import Any, List, Optional, Tuple, Type

from httplint.field.utils import BAD_DATE_SYNTAX, DATE_OBSOLETE, parse_http_date
from httplint.note import Note


def parse(value: str, now: Optional[float] = None) -> Tuple[Any, List[Type[Note]]]:
    notes: List[Type[Note]] = []

    def add_note(note: Type[Note], **kwargs: Any) -> None:
        notes.append(note)

    try:
        result = parse_http_date(value, add_note, now=now)
    except ValueError:
        result = None
    return result, notes


class HttpDateTest(unittest.TestCase):
    def test_imf_fixdate(self) -> None:
        self.assertEqual(parse("Sun, 06 Nov 1994 08:49:37 GMT"), (784111777, []))

    def test_epoch(self) -> None:
        self.assertEqual(parse("Thu, 01 Jan 1970 00:00:00 GMT"), (0, []))

    def test_obsolete_formats(self) -> None:
        now = calendar.timegm((2001, 9, 9, 1, 46, 40))  # fixed: the year is two digits
        self.assertEqual(
            parse("Sunday, 06-Nov-94 08:49:37 GMT", now), (784111777, [DATE_OBSOLETE])
        )
        self.assertEqual(parse("Sun Nov  6 08:49:37 1994"), (784111777, [DATE_OBSOLETE]))

    def test_rfc850_two_digit_year_pivot(self) -> None:
        # RFC 9110 Section 5.6.7: a two-digit year more than 50 years ahead of now is
        # the most recent past year with the same last two digits. This used to pin a
        # fixed pivot (68 -> 2068, 69 -> 1969); with a reference year of 2026, the limit
        # is 2076, so 68 is still 2068 but 77 is 1977.
        now = calendar.timegm((2026, 6, 1, 0, 0, 0))
        self.assertEqual(
            parse("Sunday, 06-Nov-68 08:49:37 GMT", now)[0],
            calendar.timegm((2068, 11, 6, 8, 49, 37)),
        )
        self.assertEqual(
            parse("Sunday, 06-Nov-69 08:49:37 GMT", now)[0],
            calendar.timegm((2069, 11, 6, 8, 49, 37)),
        )
        self.assertEqual(
            parse("Sunday, 06-Nov-77 08:49:37 GMT", now)[0],
            calendar.timegm((1977, 11, 6, 8, 49, 37)),
        )

    def test_rolling_window_boundary(self) -> None:
        # Reference: 2026-06-15 12:00:00 UTC; the limit is 2076-06-15 12:00:00.
        now = calendar.timegm((2026, 6, 15, 12, 0, 0))
        for value, expected in [
            # exactly 50 years ahead is not "more than" 50 years
            ("Monday, 15-Jun-76 12:00:00 GMT", (2076, 6, 15, 12, 0, 0)),
            # one second more is
            ("Monday, 15-Jun-76 12:00:01 GMT", (1976, 6, 15, 12, 0, 1)),
            ("Monday, 15-Jun-76 12:01:00 GMT", (1976, 6, 15, 12, 1, 0)),
            ("Monday, 15-Jun-76 13:00:00 GMT", (1976, 6, 15, 13, 0, 0)),
            ("Monday, 16-Jun-76 00:00:00 GMT", (1976, 6, 16, 0, 0, 0)),
            ("Monday, 01-Jul-76 00:00:00 GMT", (1976, 7, 1, 0, 0, 0)),
            # earlier in the same year as the limit stays in the future
            ("Monday, 15-Jun-76 11:59:59 GMT", (2076, 6, 15, 11, 59, 59)),
            ("Monday, 01-Jan-76 00:00:00 GMT", (2076, 1, 1, 0, 0, 0)),
            # 51 years ahead goes to the past, 49 years ahead stays
            ("Monday, 15-Jun-77 12:00:00 GMT", (1977, 6, 15, 12, 0, 0)),
            ("Monday, 15-Jun-75 12:00:00 GMT", (2075, 6, 15, 12, 0, 0)),
            # the current year, and just before it
            ("Monday, 15-Jun-26 12:00:00 GMT", (2026, 6, 15, 12, 0, 0)),
            ("Monday, 15-Jun-25 12:00:00 GMT", (2025, 6, 15, 12, 0, 0)),
            ("Monday, 15-Jun-99 12:00:00 GMT", (1999, 6, 15, 12, 0, 0)),
            ("Monday, 15-Jun-00 12:00:00 GMT", (2000, 6, 15, 12, 0, 0)),
        ]:
            self.assertEqual(parse(value, now), (calendar.timegm(expected), [DATE_OBSOLETE]), value)

    def test_rolling_window_reference_decades(self) -> None:
        value = "Sunday, 06-Nov-94 08:49:37 GMT"
        # The reference is the last day of the year, so that only the year decides.
        for now_year, expected_year in [
            (1900, 1894),
            (1943, 1894),
            (1944, 1994),
            (1994, 1994),
            (2000, 1994),
            (2010, 1994),
            (2043, 1994),
            (2044, 2094),
            (2060, 2094),
            (2100, 2094),
            (2143, 2094),
            (2144, 2194),
        ]:
            now = calendar.timegm((now_year, 12, 31, 12, 0, 0))
            expected = calendar.timegm((expected_year, 11, 6, 8, 49, 37))
            self.assertEqual(parse(value, now)[0], expected, now_year)

    def test_rolling_window_float_reference(self) -> None:
        # A float reference with a fractional second, as start_time can be.
        now = float(calendar.timegm((2030, 1, 1, 0, 0, 0))) + 0.5
        self.assertEqual(
            parse("Sunday, 01-Jan-80 00:00:00 GMT", now)[0],
            calendar.timegm((2080, 1, 1, 0, 0, 0)),
        )
        self.assertEqual(
            parse("Sunday, 01-Jan-81 00:00:00 GMT", now)[0],
            calendar.timegm((1981, 1, 1, 0, 0, 0)),
        )

    def test_rolling_window_leap_days(self) -> None:
        # Reference on a leap day: the limit is 29 Feb of a year 50 on, whether or not
        # that year has one.
        now = calendar.timegm((2024, 2, 29, 12, 0, 0))
        self.assertEqual(
            parse("Monday, 28-Feb-74 00:00:00 GMT", now)[0],
            calendar.timegm((2074, 2, 28, 0, 0, 0)),
        )
        self.assertEqual(
            parse("Monday, 01-Mar-74 00:00:00 GMT", now)[0],
            calendar.timegm((1974, 3, 1, 0, 0, 0)),
        )
        # A 29 February in a two-digit year that resolves to a leap year is valid.
        self.assertEqual(
            parse("Monday, 29-Feb-72 00:00:00 GMT", now)[0],
            calendar.timegm((2072, 2, 29, 0, 0, 0)),
        )
        self.assertEqual(
            parse("Monday, 29-Feb-76 00:00:00 GMT", now)[0],
            calendar.timegm((1976, 2, 29, 0, 0, 0)),
        )
        # A reference in an ordinary year, and a leap-day date at the limit.
        now = calendar.timegm((2026, 2, 28, 0, 0, 0))
        self.assertEqual(
            parse("Monday, 29-Feb-76 00:00:00 GMT", now)[0],
            calendar.timegm((1976, 2, 29, 0, 0, 0)),
        )

    def test_rolling_window_century_leap_year(self) -> None:
        # 00 resolves to 2000, a leap year.
        now = calendar.timegm((2026, 6, 1, 0, 0, 0))
        self.assertEqual(
            parse("Tuesday, 29-Feb-00 00:00:00 GMT", now)[0],
            calendar.timegm((2000, 2, 29, 0, 0, 0)),
        )

    def test_rolling_window_century_non_leap_year(self) -> None:
        # 00 resolves to 2100, which is not a leap year, so 29 February doesn't exist.
        now = calendar.timegm((2060, 6, 1, 0, 0, 0))
        result, notes = parse("Monday, 29-Feb-00 00:00:00 GMT", now)
        self.assertIsNone(result)  # 2100-02-29 doesn't exist
        self.assertIn(BAD_DATE_SYNTAX, notes)

    def test_two_digit_year_defaults_to_wall_clock(self) -> None:
        # Without a reference, "now" is the current time: this year's last two digits
        # resolve to this year.
        this_year = time.gmtime().tm_year
        value = f"Sunday, 01-Jan-{this_year % 100:02d} 00:00:00 GMT"
        self.assertEqual(parse(value)[0], calendar.timegm((this_year, 1, 1, 0, 0, 0)))

    def test_four_digit_and_asctime_years_ignore_reference(self) -> None:
        now = calendar.timegm((2026, 6, 1, 0, 0, 0))
        for ref in [now, calendar.timegm((1950, 1, 1, 0, 0, 0)), 0]:
            self.assertEqual(parse("Sun, 06 Nov 2094 08:49:37 GMT", ref)[0], 3939871777)
            self.assertEqual(
                parse("Sun Nov  6 08:49:37 1994", ref),
                (784111777, [DATE_OBSOLETE]),
            )

    def test_unusable_reference_falls_back(self) -> None:
        # A timestamp gmtime can't represent is ignored in favour of the wall clock.
        this_year = time.gmtime().tm_year
        value = f"Sunday, 01-Jan-{this_year % 100:02d} 00:00:00 GMT"
        expected = calendar.timegm((this_year, 1, 1, 0, 0, 0))
        self.assertEqual(parse(value, 1e30)[0], expected)
        self.assertEqual(parse(value, float("nan"))[0], expected)

    def test_year_zero(self) -> None:
        # Used to come out as year 2000.
        self.assertEqual(parse("Mon, 01 Jan 0000 00:00:00 GMT"), (None, [BAD_DATE_SYNTAX]))
        self.assertEqual(
            parse("Sat Jan  1 00:00:00 0000"), (None, [DATE_OBSOLETE, BAD_DATE_SYNTAX])
        )

    def test_four_digit_years_are_not_pivoted(self) -> None:
        # parsedate would read these as 1999 and 1969.
        self.assertEqual(
            parse("Fri, 01 Jan 0099 00:00:00 GMT")[0], calendar.timegm((99, 1, 1, 0, 0, 0))
        )
        self.assertEqual(
            parse("Wed, 01 Jan 0069 00:00:00 GMT")[0], calendar.timegm((69, 1, 1, 0, 0, 0))
        )
        self.assertEqual(parse("Fri, 31 Dec 9999 23:59:59 GMT")[0], 253402300799)

    def test_impossible_dates(self) -> None:
        for value in [
            "Mon, 31 Feb 2011 25:61:61 GMT",
            "Mon, 31 Feb 2011 00:00:00 GMT",
            "Mon, 29 Feb 2011 00:00:00 GMT",
            "Mon, 00 Jan 2011 00:00:00 GMT",
            "Mon, 32 Jan 2011 00:00:00 GMT",
            "Mon, 31 Apr 2011 00:00:00 GMT",
            "Mon, 01 Jan 2011 24:00:00 GMT",
            "Mon, 01 Jan 2011 00:60:00 GMT",
            "Mon, 01 Jan 2011 00:00:61 GMT",
            "Monday, 31-Feb-11 00:00:00 GMT",
            "Mon Feb 31 00:00:00 2011",
        ]:
            result, notes = parse(value)
            self.assertIsNone(result, value)
            self.assertIn(BAD_DATE_SYNTAX, notes, value)
            self.assertEqual(len([n for n in notes if n is BAD_DATE_SYNTAX]), 1, value)

    def test_leap_day_and_leap_second(self) -> None:
        self.assertEqual(parse("Wed, 29 Feb 2012 00:00:00 GMT")[0], 1330473600)
        self.assertEqual(parse("Sat, 30 Jun 2012 23:59:60 GMT")[0], 1341100800)


if __name__ == "__main__":
    unittest.main()
