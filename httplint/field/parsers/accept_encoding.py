from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class accept_encoding(HttpField):
    canonical_name = "Accept-Encoding"
    description = """\
The `Accept-Encoding` header field can be used by user agents to indicate what response content-codings are
acceptable in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-encoding"
    syntax = rfc9110.Accept_Encoding
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AcceptEncodingTest(FieldTest):
    name = "Accept-Encoding"
    inputs = [b"gzip;q=1.0, identity; q=0.5, *;q=0"]
    expected_out = ["gzip;q=1.0", "identity; q=0.5", "*;q=0"]
