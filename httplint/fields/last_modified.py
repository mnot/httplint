from . import HttpField, FieldTest
from ..syntax import rfc7232
from ..type import AddNoteMethodType
from ._notes import BAD_DATE_SYNTAX
from ._utils import parse_date


class last_modified(HttpField):
    canonical_name = "Last-Modified"
    description = """\
The `Last-Modified` header indicates the time that the origin server believes the
representation was last modified."""
    reference = f"{rfc7232.SPEC_URL}#header.last_modified"
    syntax = False  # rfc7232.Last_Modified
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_date(field_value, add_note)


class BasicLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b"0"]
    expected_out = None
    expected_err = [BAD_DATE_SYNTAX]


class BlankLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b""]
    expected_out = None
    expected_err = [BAD_DATE_SYNTAX]
