from typing import cast

from httplint.field.singleton_field import SingletonField
from httplint.field.cors import check_preflight_response, CORS_PREFLIGHT_ONLY
from httplint.field.tests import FieldTest, FakeRequest
from httplint.message import HttpMessageLinter
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import categories


class access_control_max_age(SingletonField):
    canonical_name = "Access-Control-Max-Age"
    description = """\
The `Access-Control-Max-Age` response header indicates how long the results of a CORS preflight
request (as scoped by the `Access-Control-Allow-Methods` and
`Access-Control-Allow-Headers` request headers) can be cached."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-max-age"
    syntax = rfc9110.delay_seconds
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_preflight_response(self.message, self.canonical_name, add_note)


class AccessControlMaxAgeTest(FieldTest):
    name = "Access-Control-Max-Age"
    inputs = [b"600"]
    expected_out = "600"


class AccessControlMaxAgePreflightTest(FieldTest):
    name = "Access-Control-Max-Age"
    inputs = [b"600"]
    expected_out = "600"
    expected_notes = [CORS_PREFLIGHT_ONLY]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.related = cast(HttpMessageLinter, FakeRequest())


class AccessControlMaxAgeValidPreflightTest(FieldTest):
    name = "Access-Control-Max-Age"
    inputs = [b"600"]
    expected_out = "600"

    def set_context(self, message: HttpMessageLinter) -> None:
        request = FakeRequest()
        request.method = "OPTIONS"
        request.headers.text = [
            ("origin", "example.com"),
            ("access-control-request-method", "GET"),
        ]
        message.related = cast(HttpMessageLinter, request)
