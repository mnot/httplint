from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class accept_language(HttpField):
    canonical_name = "Accept-Language"
    description = """\
The `Accept-Language` header field can be used by user agents to indicate the set of natural languages that are
preferred in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-language"
    syntax = rfc9110.Accept_Language
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AcceptLanguageTest(FieldTest):
    name = "Accept-Language"
    inputs = [b"da, en-gb;q=0.8, en;q=0.7"]
    expected_out = ["da", "en-gb;q=0.8", "en;q=0.7"]
