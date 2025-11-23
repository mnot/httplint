from typing import List, Tuple

from httplint.field import HttpField
from httplint.field.cors import (
    check_preflight_request_header,
    CORS_PREFLIGHT_REQ_METHOD_WRONG,
    CORS_PREFLIGHT_REQ_NO_ORIGIN,
    CORS_PREFLIGHT_REQ_NO_METHOD,
)
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.message import HttpMessageLinter
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
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_preflight_request_header(self.message, self.canonical_name, add_note)


class AccessControlRequestHeadersTest(FieldTest):
    name = "Access-Control-Request-Headers"
    inputs = [b"Custom-Header, Upgrade-Insecure-Requests"]
    expected_out = ["Custom-Header", "Upgrade-Insecure-Requests"]


class AccessControlRequestHeadersPreflightTest(FieldTest):
    name = "Access-Control-Request-Headers"
    inputs = [b"a, b"]
    expected_out = ["a", "b"]
    request_method: str
    request_headers: List[Tuple[bytes, bytes]]

    def set_context(self, message: HttpMessageLinter) -> None:
        # Override message with a request linter
        self.message = FakeRequestLinter()
        self.message.method = getattr(self, "request_method", "OPTIONS")
        headers = getattr(
            self,
            "request_headers",
            [
                (b"Origin", b"http://example.com"),
            ],
        )
        self.message.headers.parsed = {}  # Clear existing headers to avoid repeat note
        self.message.headers.handlers = {}

        # Workaround for SINGLE_HEADER_REPEAT: manually populate parsed for Method
        # and remove from process list
        process_headers = []
        for name, value in headers:
            if name.lower() == b"access-control-request-method":
                self.message.headers.parsed["access-control-request-method"] = (
                    value.decode("ascii")
                )
            else:
                process_headers.append((name, value))

        self.message.headers.process(process_headers)

    def test_header(self) -> None:
        pass

    def test_wrong_method(self) -> None:
        self.request_method = "GET"
        self.request_headers = [
            (b"Origin", b"http://example.com"),
            (b"Access-Control-Request-Method", b"GET"),
        ]
        self.assert_note(b"a, b", CORS_PREFLIGHT_REQ_METHOD_WRONG, ["a", "b"])

    def test_no_origin(self) -> None:
        self.request_headers = [(b"Access-Control-Request-Method", b"GET")]
        self.assert_note(b"a, b", CORS_PREFLIGHT_REQ_NO_ORIGIN, ["a", "b"])

    def test_no_method(self) -> None:
        self.request_headers = [(b"Origin", b"http://example.com")]
        self.assert_note(b"a, b", CORS_PREFLIGHT_REQ_NO_METHOD, ["a", "b"])
