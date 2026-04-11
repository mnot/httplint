from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)


class access_control_allow_methods(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Access-Control-Allow-Methods"
    description = """\
The `Access-Control-Allow-Methods` response header specifies the method or methods allowed when
accessing the resource in response to a CORS preflight request."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-methods"
    syntax = rfc9110.token
    category = categories.CORS
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value


class AccessControlAllowMethodsTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Allow-Methods"
    inputs = [b"GET, PUT, DELETE"]
    expected_out = ["GET", "PUT", "DELETE"]
    expected_notes: NoteClassListType = [CORS_PREFLIGHT_ONLY]
