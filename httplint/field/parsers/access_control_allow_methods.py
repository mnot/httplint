from typing import cast

from httplint.field import HttpField
from httplint.field.cors import check_preflight_response, CORS_PREFLIGHT_ONLY
from httplint.field.tests import FieldTest, FakeRequest
from httplint.message import HttpMessageLinter
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class access_control_allow_methods(HttpField):
    canonical_name = "Access-Control-Allow-Methods"
    description = """\
The `Access-Control-Allow-Methods` response header specifies the method or methods allowed when
accessing the resource in response to a CORS preflight request."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-methods"
    syntax = rfc9110.token
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_preflight_response(self.message, self.canonical_name, add_note)


class AccessControlAllowMethodsTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"POST, GET, OPTIONS"]
    expected_out = ["POST", "GET", "OPTIONS"]


class AccessControlAllowMethodsPreflightTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"POST"]
    expected_out = ["POST"]
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.related = cast(HttpMessageLinter, FakeRequest())


class AccessControlAllowMethodsValidPreflightTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"POST"]
    expected_out = ["POST"]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = FakeRequest()
        request.method = "OPTIONS"
        request.headers.text = [
            ("origin", "example.com"),
            ("access-control-request-method", "GET"),
        ]
        message.related = cast(HttpMessageLinter, request)
