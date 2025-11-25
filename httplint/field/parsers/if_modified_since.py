from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class if_modified_since(HttpField):
    canonical_name = "If-Modified-Since"
    description = """\
The `If-Modified-Since` header field makes a request method conditional on the
selected representation's modification date being more recent than the date provided in the
field-value."""
    reference = f"{rfc9110.SPEC_URL}#field.if-modified-since"
    syntax = rfc9110.If_Modified_Since
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class IfModifiedSinceTest(FieldTest):
    name = "If-Modified-Since"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = "Sat, 29 Oct 1994 19:43:31 GMT"
