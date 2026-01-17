from httplint.field import HttpField
from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.note import categories
from httplint.types import AddNoteMethodType


class access_control_allow_methods(HttpField):
    canonical_name = "Access-Control-Allow-Methods"
    description = """\
The `Access-Control-Allow-Methods` response header specifies the method or methods allowed when
accessing the resource in response to a CORS preflight request."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-methods"
    syntax = rfc9110.token
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: "AddNoteMethodType") -> str:
        return field_value


class AccessControlAllowMethodsTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"GET, PUT, DELETE"]
    expected_out = ["GET", "PUT", "DELETE"]
    expected_notes = [CORS_PREFLIGHT_ONLY]
