from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType
from httplint.field.notes import BAD_DATE_SYNTAX
from httplint.field.utils import parse_http_date


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
