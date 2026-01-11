from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class if_range(SingletonField):
    canonical_name = "If-Range"
    description = """\
The `If-Range` header field allows a client to "short-circuit" the second request. It means: if
the representation is unchanged, send me the part(s) that I am missing; otherwise, send me the
entire new representation."""
    reference = f"{rfc9110.SPEC_URL}#field.if-range"
    syntax = rfc9110.If_Range
    category = categories.VALIDATION
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class IfRangeTest(FieldTest):
    name = "If-Range"
    inputs = [b'"xyzzy"']
    expected_out = '"xyzzy"'
