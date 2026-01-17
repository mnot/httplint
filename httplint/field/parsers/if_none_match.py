from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import categories


class if_none_match(HttpListField):
    canonical_name = "If-None-Match"
    description = """\
The `If-None-Match` header field makes the request method conditional on the
absence of a matching entity tag, or if the field-value is "*", the absence of
any current representation of the target resource."""
    reference = f"{rfc9110.SPEC_URL}#field.if-none-match"
    syntax = rfc9110.If_None_Match
    category = categories.VALIDATION
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class IfNoneMatchTest(FieldTest):
    name = "If-None-Match"
    inputs = [b'W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"']
    expected_out = ['W/"xyzzy"', 'W/"r2d2xxxx"', 'W/"c3piozzzz"']
