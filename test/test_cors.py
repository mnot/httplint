from typing import List, Tuple, cast
import unittest

from httplint.field.cors import (
    ACAO_MULTIPLE_VALUES,
    ACAC_NOT_TRUE,
    CORS_PREFLIGHT_ONLY,
    CORS_PREFLIGHT_RESPONSE,
    CORS_PREFLIGHT_REQ_METHOD_WRONG,
    CORS_PREFLIGHT_REQ_NO_ORIGIN,
    CORS_PREFLIGHT_REQ_NO_METHOD,
    CORS_PREFLIGHT_REQUEST,
)
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.message import HttpMessageLinter, HttpRequestLinter


class AccessControlAllowOriginMultipleTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"https://foo.com, https://bar.com"]
    expected_out = "https://foo.com, https://bar.com"
    expected_notes = [ACAO_MULTIPLE_VALUES, BAD_SYNTAX]


class AccessControlAllowHeadersPreflightTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"a, b"]
    expected_out = ["a", "b"]
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def setUp(self) -> None:
        super().setUp()
        self.message.method = "OPTIONS"  # type: ignore


class AccessControlAllowHeadersValidPreflightTest(FieldTest):
    name = "Access-Control-Allow-Headers"
    inputs = [b"a, b"]
    expected_out = ["a", "b"]
    expected_notes = [CORS_PREFLIGHT_RESPONSE]

    def setUp(self) -> None:
        super().setUp()
        self.message.related.method = "OPTIONS"  # type: ignore
        self.message.related.headers.text = [  # type: ignore
            ("Origin", "http://example.com"),
            ("Access-Control-Request-Method", "POST"),
        ]
        self.message.related.headers.parsed = {  # type: ignore
            "origin": "http://example.com",
            "access-control-request-method": "POST",
        }


class AccessControlAllowMethodsPreflightTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"GET, PUT, DELETE"]
    expected_out = ["GET", "PUT", "DELETE"]
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def setUp(self) -> None:
        super().setUp()
        self.message.method = "OPTIONS"  # type: ignore


class AccessControlAllowMethodsValidPreflightTest(FieldTest):
    name = "Access-Control-Allow-Methods"
    inputs = [b"GET, PUT, DELETE"]
    expected_out = ["GET", "PUT", "DELETE"]
    expected_notes = [CORS_PREFLIGHT_RESPONSE]

    def setUp(self) -> None:
        super().setUp()
        self.message.related.method = "OPTIONS"  # type: ignore
        self.message.related.headers.text = [  # type: ignore
            ("Origin", "http://example.com"),
            ("Access-Control-Request-Method", "POST"),
        ]
        self.message.related.headers.parsed = {  # type: ignore
            "origin": "http://example.com",
            "access-control-request-method": "POST",
        }


class AccessControlMaxAgePreflightTest(FieldTest):
    name = "Access-Control-Max-Age"
    inputs = [b"123"]
    expected_out = 123
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def setUp(self) -> None:
        super().setUp()
        self.message.method = "OPTIONS"  # type: ignore


class AccessControlMaxAgeValidPreflightTest(FieldTest):
    name = "Access-Control-Max-Age"
    inputs = [b"123"]
    expected_out = 123
    expected_notes = [CORS_PREFLIGHT_RESPONSE]

    def setUp(self) -> None:
        super().setUp()
        self.message.related.method = "OPTIONS"  # type: ignore
        self.message.related.headers.text = [  # type: ignore
            ("Origin", "http://example.com"),
            ("Access-Control-Request-Method", "POST"),
        ]
        self.message.related.headers.parsed = {  # type: ignore
            "origin": "http://example.com",
            "access-control-request-method": "POST",
        }


class AccessControlRequestMethodPreflightTest(FieldTest):
    name = "Access-Control-Request-Method"
    inputs = [b"GET"]
    expected_out = "GET"
    expected_notes = [CORS_PREFLIGHT_REQUEST]
    request_method = "OPTIONS"
    request_headers = [(b"Origin", b"http://example.com")]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, self.message)
        request.method = self.request_method
        self.message.headers.parsed = {}  # Clear parsed to avoid side effects
        self.message.headers.process(self.request_headers)


class AccessControlRequestMethodWrongTest(AccessControlRequestMethodPreflightTest):
    request_method = "GET"
    expected_notes = [CORS_PREFLIGHT_REQ_METHOD_WRONG]


class AccessControlRequestMethodNoOriginTest(AccessControlRequestMethodPreflightTest):
    request_headers: List[Tuple[bytes, bytes]] = []
    expected_notes = [CORS_PREFLIGHT_REQ_NO_ORIGIN]


class AccessControlRequestHeadersPreflightTest(FieldTest):
    name = "Access-Control-Request-Headers"
    inputs = [b"a, b"]
    expected_out = ["a", "b"]
    request_method = "OPTIONS"
    request_headers = [(b"Origin", b"http://example.com")]

    def set_context(self, message: HttpMessageLinter) -> None:
        self.message.headers.parsed = {}  # Clear existing headers to avoid repeat note
        self.message.headers.handlers = {}

        # Workaround for SINGLE_HEADER_REPEAT: manually populate parsed for Method
        # and remove from process list
        process_headers = []
        for name, value in self.request_headers:
            if name.lower() == b"access-control-request-method":
                self.message.headers.parsed["access-control-request-method"] = value.decode("ascii")
            else:
                process_headers.append((name, value))

        request = cast(HttpRequestLinter, self.message)
        request.method = self.request_method
        self.message.headers.process(process_headers)

    def test_header(self) -> None:
        pass


class AccessControlRequestHeadersWrongMethodTest(AccessControlRequestHeadersPreflightTest):
    request_method = "GET"
    request_headers = [
        (b"Origin", b"http://example.com"),
        (b"Access-Control-Request-Method", b"GET"),
    ]
    expected_notes = [CORS_PREFLIGHT_REQ_METHOD_WRONG]

    def test_header(self) -> None:
        self.assert_note(b"a, b", self.expected_notes[0], ["a", "b"])


class AccessControlRequestHeadersNoOriginTest(AccessControlRequestHeadersPreflightTest):
    request_headers = [(b"Access-Control-Request-Method", b"GET")]
    expected_notes = [CORS_PREFLIGHT_REQ_NO_ORIGIN]

    def test_header(self) -> None:
        self.assert_note(b"a, b", self.expected_notes[0], ["a", "b"])


class AccessControlRequestHeadersNoMethodTest(AccessControlRequestHeadersPreflightTest):
    request_headers = [(b"Origin", b"http://example.com")]
    expected_notes = [CORS_PREFLIGHT_REQ_NO_METHOD]

    def test_header(self) -> None:
        self.assert_note(b"a, b", self.expected_notes[0], ["a", "b"])


if __name__ == "__main__":
    unittest.main()