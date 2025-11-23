from typing import List, Tuple

from httplint.field import HttpField
from httplint.field.cors import (
    check_preflight_request_header,
    CORS_PREFLIGHT_REQ_METHOD_WRONG,
    CORS_PREFLIGHT_REQ_NO_ORIGIN,
)
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.message import HttpMessageLinter
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class access_control_request_method(HttpField):
    canonical_name = "Access-Control-Request-Method"
    description = """\
The `Access-Control-Request-Method` request header is used by browsers when issuing a CORS
preflight request, to let the server know which HTTP method will be used when the actual request
is made."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-request-method"
    syntax = rfc9110.token
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_preflight_request_header(self.message, self.canonical_name, add_note)


class AccessControlRequestMethodTest(FieldTest):
    name = "Access-Control-Request-Method"
    inputs = [b"POST"]
    expected_out = "POST"


class AccessControlRequestMethodPreflightTest(FieldTest):
    name = "Access-Control-Request-Method"
    inputs = [b"GET"]
    expected_out = "GET"
    request_method: str
    request_headers: List[Tuple[bytes, bytes]]

    def set_context(self, message: HttpMessageLinter) -> None:
        # Override message with a request linter
        self.message = FakeRequestLinter()
        self.message.method = getattr(self, "request_method", "OPTIONS")
        headers = getattr(self, "request_headers", [(b"Origin", b"http://example.com")])
        self.message.headers.process(headers)

    def test_wrong_method(self) -> None:
        self.request_method = "GET"
        self.assert_note(b"GET", CORS_PREFLIGHT_REQ_METHOD_WRONG, "GET")

    def test_no_origin(self) -> None:
        self.request_headers: List[Tuple[bytes, bytes]] = []
        self.assert_note(b"GET", CORS_PREFLIGHT_REQ_NO_ORIGIN, "GET")
