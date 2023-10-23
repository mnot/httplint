from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7234
from httplint.types import AddNoteMethodType
from httplint.field.notes import BAD_DATE_SYNTAX
from httplint.field.utils import parse_http_date


class expires(HttpField):
    canonical_name = "Expires"
    description = """\
The `Expires` response header gives a time after which the response is considered stale by
caches."""
    reference = f"{rfc7234.SPEC_URL}#header.expires"
    syntax = False  # rfc7234.Expires
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(field_value, add_note)


class BasicExpiresTest(FieldTest):
    name = "Expires"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadExpiresTest(FieldTest):
    name = "Expires"
    inputs = [b"0"]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]


class BlankExpiresTest(FieldTest):
    name = "Expires"
    inputs = [b""]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]
