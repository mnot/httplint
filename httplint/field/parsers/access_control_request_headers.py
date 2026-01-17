from typing import cast

from httplint.field import HttpField
from httplint.field.cors import CORS_PREFLIGHT_REQUEST
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter, HttpRequestLinter
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class access_control_request_headers(HttpField):
    canonical_name = "Access-Control-Request-Headers"
    description = """\
The `Access-Control-Request-Headers` request header is used by browsers when issuing a CORS
preflight request, to let the server know which HTTP headers the client might send when the actual
request is made."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-request-headers"
    syntax = rfc9110.token
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: "AddNoteMethodType") -> str:
        return field_value.lower()


class AccessControlRequestHeadersTest(FieldTest):
    name = "Access-Control-Request-Headers"
    inputs = [b"Custom-Header, Upgrade-Insecure-Requests"]
    expected_out = ["custom-header", "upgrade-insecure-requests"]
    expected_notes = [CORS_PREFLIGHT_REQUEST]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, message)
        request.method = "OPTIONS"
        # Manually populate parsed headers to avoid triggering notes on context headers
        message.headers.parsed["origin"] = "http://example.com"
        message.headers.parsed["access-control-request-method"] = "POST"
