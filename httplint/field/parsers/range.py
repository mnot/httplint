from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class range(SingletonField):  # pylint: disable=redefined-builtin
    canonical_name = "Range"
    description = """\
The `Range` header field on a GET request modifies the method semantics to request only those
parts of the representation that are specified."""
    reference = f"{rfc9110.SPEC_URL}#field.range"
    syntax = rfc9110.Range
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class RangeTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=0-499"]
    expected_out = "bytes=0-499"
