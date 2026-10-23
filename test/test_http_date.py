"""
parse_http_date must reject dates that don't exist rather than normalising them, and
must not apply a two-digit-year pivot to four-digit years.
"""

import calendar
import unittest
from typing import Any, List, Tuple, Type

from httplint.field.utils import BAD_DATE_SYNTAX, DATE_OBSOLETE, parse_http_date
from httplint.note import Note


def parse(value: str) -> Tuple[Any, List[Type[Note]]]:
    notes: List[Type[Note]] = []

    def add_note(note: Type[Note], **kwargs: Any) -> None:
        notes.append(note)

    try:
        result = parse_http_date(value, add_note)
    except ValueError:
        result = None
    return result, notes


class HttpDateTest(unittest.TestCase):
    def test_imf_fixdate(self) -> None:
        self.assertEqual(parse("Sun, 06 Nov 1994 08:49:37 GMT"), (784111777, []))

    def test_epoch(self) -> None:
        self.assertEqual(parse("Thu, 01 Jan 1970 00:00:00 GMT"), (0, []))

    def test_obsolete_formats(self) -> None:
        self.assertEqual(parse("Sunday, 06-Nov-94 08:49:37 GMT"), (784111777, [DATE_OBSOLETE]))
        self.assertEqual(parse("Sun Nov  6 08:49:37 1994"), (784111777, [DATE_OBSOLETE]))

    def test_rfc850_two_digit_year_pivot(self) -> None:
        self.assertEqual(
            parse("Sunday, 06-Nov-68 08:49:37 GMT")[0], calendar.timegm((2068, 11, 6, 8, 49, 37))
        )
        self.assertEqual(
            parse("Sunday, 06-Nov-69 08:49:37 GMT")[0], calendar.timegm((1969, 11, 6, 8, 49, 37))
        )

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
