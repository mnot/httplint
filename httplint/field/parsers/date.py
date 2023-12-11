from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType
from httplint.util import relative_time
from httplint.field.notes import Note, categories, levels, BAD_DATE_SYNTAX
from httplint.field.utils import parse_http_date

MAX_CLOCK_SKEW = 5  # seconds


class date(HttpField):
    canonical_name = "Date"
    description = """\
The `Date` header represents the time when the message was generated, regardless of caching that
happened since.

It is used by caches as input to expiration calculations, and to detect clock drift."""
    reference = f"{rfc7231.SPEC_URL}#header.date"
    syntax = False  # rfc7231.Date
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(field_value, add_note)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if (
            self.message.message_type == "response"
            and self.message.start_time
            and self.value
        ):
            age_value = self.message.headers.parsed.get("age", 0) or 0
            skew = self.value - int(self.message.start_time) + age_value
            if age_value > MAX_CLOCK_SKEW > (age_value - skew):
                self.message.notes.add("header-date header-age", AGE_PENALTY)
            elif abs(skew) > MAX_CLOCK_SKEW:
                add_note(
                    DATE_INCORRECT,
                    clock_skew_string=relative_time(skew, 0, 2),
                )
            else:
                add_note(DATE_CORRECT)


class DATE_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    _summary = "The server's clock is correct."
    _text = """\
HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
compared to the local clock, the server's clock appears to be well-synchronised."""


class DATE_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The server's clock is %(clock_skew_string)s."
    _text = """\
Compared to the local clock, the server's clock does not appear to be well-synchronised.

HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
clock skew can cause responses that should be cacheable to be considered uncacheable (especially if
their freshness lifetime is short).

Ask your server administrator to synchronise the clock, e.g., using
[NTP](http://en.wikipedia.org/wiki/Network_Time_Protocol Network Time Protocol).

Apparent clock skew can also be caused by caching the response without adjusting the `Age` header;
e.g., in a reverse proxy or Content Delivery network. See [this
paper](https://www.usenix.org/legacy/events/usits01/full_papers/cohen/cohen_html/index.html) for more information. """  # pylint: disable=line-too-long


class AGE_PENALTY(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "It appears that the Date header has been changed by an intermediary."
    _text = """\
It appears that this response has been cached by a reverse proxy or Content Delivery Network,
because the `Age` header is present, but the `Date` header is more recent than it indicates.

Generally, reverse proxies should either omit the `Age` header (if they have another means of
determining how fresh the response is), or leave the `Date` header alone (i.e., act as a normal
HTTP cache).

See [this paper](http://j.mp/S7lPL4) for more information."""


class BasicDateTest(FieldTest):
    name = "Date"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadDateTest(FieldTest):
    name = "Date"
    inputs = [b"0"]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]


class BlankDateTest(FieldTest):
    name = "Date"
    inputs = [b""]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]
