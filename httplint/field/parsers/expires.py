from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9111
from httplint.types import AddNoteMethodType
from httplint.field.utils import BAD_DATE_SYNTAX
from httplint.field.utils import parse_http_date
from httplint.note import categories


class expires(SingletonField):
    canonical_name = "Expires"
    description = """\
The `Expires` response header gives a time after which the response is considered stale by
caches."""
    reference = f"{rfc9111.SPEC_URL}#field.expires"
    syntax = False  # rfc9111.Expires
    category = categories.CACHING
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(field_value, add_note, category=self.category)


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


class ExpiresYearBigTest(FieldTest):
    name = "Expires"
    inputs = [b"Fri, 31 Dec 9999 23:59:59 GMT"]
    expected_out = 253402300799
