from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class from_field(SingletonField):
    canonical_name = "From"
    description = """\
The `From` header field contains an Internet email address for the human user who controls the
requesting user agent."""
    reference = f"{rfc9110.SPEC_URL}#field.from"
    syntax = rfc9110.From
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class FromTest(FieldTest):
    name = "From"
    inputs = [b"webmaster@example.org"]
    expected_out = "webmaster@example.org"
