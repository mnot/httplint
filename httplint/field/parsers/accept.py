from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class accept(HttpField):
    canonical_name = "Accept"
    description = """\
The `Accept` header field can be used by user agents to specify response media types that are
acceptable in responses."""
    reference = f"{rfc9110.SPEC_URL}#field.accept"
    syntax = rfc9110.Accept
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AcceptTest(FieldTest):
    name = "Accept"
    inputs = [b"audio/*; q=0.2, audio/basic"]
    expected_out = ["audio/*; q=0.2", "audio/basic"]
