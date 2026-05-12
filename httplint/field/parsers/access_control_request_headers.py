from httplint.field.cors import CORS_PREFLIGHT_REQUEST
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
)


class access_control_request_headers(HttpListField[RequestLinterProtocol]):
    canonical_name = "Access-Control-Request-Headers"
    description = """\
The `Access-Control-Request-Headers` request header is used by browsers when issuing a CORS
preflight request, to let the server know which HTTP headers the client might send when the actual
request is made."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-request-headers"
    syntax = rfc9110.token
    category = categories.CORS
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()


class AccessControlRequestHeadersTest(FieldTest[RequestLinterProtocol]):
    name = "Access-Control-Request-Headers"
    inputs = [b"Custom-Header, Upgrade-Insecure-Requests"]
    expected_out = ["custom-header", "upgrade-insecure-requests"]
    expected_notes: NoteClassListType = [CORS_PREFLIGHT_REQUEST]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.method = "OPTIONS"
        # Manually populate parsed headers to avoid triggering notes on context headers
        message.headers.parsed["origin"] = "http://example.com"
        message.headers.parsed["access-control-request-method"] = "POST"
