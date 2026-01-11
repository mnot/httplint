from typing import cast

from httplint.field import HttpField
from httplint.field.cors import check_preflight_response, CORS_PREFLIGHT_ONLY
from httplint.field.tests import FieldTest, FakeRequest
from httplint.message import HttpMessageLinter
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import categories


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

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_preflight_response(self.message, self.canonical_name, add_note)


class AccessControlAllowHeadersTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"Custom-Header, Upgrade-Insecure-Requests"]
    expected_out = ["Custom-Header", "Upgrade-Insecure-Requests"]


class AccessControlAllowHeadersPreflightTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"Custom-Header"]
    expected_out = ["Custom-Header"]
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.related = cast(HttpMessageLinter, FakeRequest())


class AccessControlAllowHeadersValidPreflightTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"Custom-Header"]
    expected_out = ["Custom-Header"]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = FakeRequest()
        request.method = "OPTIONS"
        request.headers.text = [
            ("origin", "example.com"),
            ("access-control-request-method", "GET"),
        ]
        message.related = cast(HttpMessageLinter, request)
