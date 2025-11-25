from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class max_forwards(HttpField):
    canonical_name = "Max-Forwards"
    description = """\
The `Max-Forwards` header field provides a mechanism to limit
the number of times that the request is forwarded by intermediaries."""
    reference = f"{rfc9110.SPEC_URL}#field.max-forwards"
    syntax = rfc9110.Max_Forwards
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class MaxForwardsTest(FieldTest):
    name = "Max-Forwards"
    inputs = [b"5"]
    expected_out = "5"
