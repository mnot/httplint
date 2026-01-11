from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class if_unmodified_since(SingletonField):
    canonical_name = "If-Unmodified-Since"
    description = """\
The `If-Unmodified-Since` header field makes the request method conditional on the selected
representation's last modification date being earlier than or equal to the date provided in the
field-value."""
    reference = f"{rfc9110.SPEC_URL}#field.if-unmodified-since"
    syntax = rfc9110.If_Unmodified_Since
    category = categories.VALIDATION
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class IfUnmodifiedSinceTest(FieldTest):
    name = "If-Unmodified-Since"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = "Sat, 29 Oct 1994 19:43:31 GMT"
