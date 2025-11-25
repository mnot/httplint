from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class if_match(HttpField):
    canonical_name = "If-Match"
    description = """\
The `If-Match` header field makes the request method conditional on the recipient origin server
having a current representation of the target resource."""
    reference = f"{rfc9110.SPEC_URL}#field.if-match"
    syntax = rfc9110.If_Match
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class IfMatchTest(FieldTest):
    name = "If-Match"
    inputs = [b'"xyzzy", "r2d2xxxx", "c3piozzzz"']
    expected_out = ['"xyzzy"', '"r2d2xxxx"', '"c3piozzzz"']
