from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class expect(HttpField):
    canonical_name = "Expect"
    description = """\
The `Expect` header field in a request indicates behaviors (expectations) that need to be
fulfilled by the server in order to properly handle the request."""
    reference = f"{rfc9110.SPEC_URL}#field.expect"
    syntax = rfc9110.Expect
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ExpectTest(FieldTest):
    name = "Expect"
    inputs = [b"100-continue"]
    expected_out = ["100-continue"]
