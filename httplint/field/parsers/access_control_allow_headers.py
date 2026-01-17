from httplint.field import HttpField
from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.note import categories
from httplint.types import AddNoteMethodType


class access_control_allow_headers(HttpField):
    canonical_name = "Access-Control-Allow-Headers"
    description = """\
The `Access-Control-Allow-Headers` response header is used in response to a CORS preflight
request to indicate which HTTP headers can be used during the actual request."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-headers"
    syntax = rfc9110.token
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: "AddNoteMethodType") -> str:
        return field_value.lower()


class AccessControlAllowHeadersTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"a, b"]
    expected_out = ["a", "b"]
    expected_notes = [CORS_PREFLIGHT_ONLY]
