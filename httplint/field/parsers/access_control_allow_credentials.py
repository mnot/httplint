from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, levels, categories
from httplint.types import AddNoteMethodType


class access_control_allow_credentials(HttpField):
    canonical_name = "Access-Control-Allow-Credentials"
    description = """\
The `Access-Control-Allow-Credentials` response header tells browsers whether to expose the response
to frontend code when the request's credentials mode (`Request.credentials`) is
`include`."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-credentials"
    syntax = False
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if field_value != "true":
            add_note(ACAC_NOT_TRUE)
        return field_value


class ACAC_NOT_TRUE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "Access-Control-Allow-Credentials must be 'true'."
    _text = """\
The `Access-Control-Allow-Credentials` header must be set to `true` if present. If you don't want
to allow credentials, omit the header."""


class AccessControlAllowCredentialsTest(FieldTest):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"true"]
    expected_out = "true"

    def test_not_true(self) -> None:
        self.inputs = [b"false"]
        self.expected_notes = [ACAC_NOT_TRUE]
        self.expected_out = "false"
        self.setUp()
        self.test_header()
