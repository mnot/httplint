from typing import cast

from httplint.field.singleton_field import SingletonField
from httplint.field.cors import (
    CORS_ORIGIN_MATCH,
    CORS_ORIGIN_MISMATCH,
    CORS_ORIGIN_NULL,
    CORS_ORIGIN_STAR,
    check_access_control_allow_origin,
)
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter, HttpRequestLinter, HttpResponseLinter
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class access_control_allow_origin(SingletonField):
    canonical_name = "Access-Control-Allow-Origin"
    description = """\
The `Access-Control-Allow-Origin` response header indicates whether the response can be shared with
requesting code from the given origin."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-origin"
    syntax = rf"(?:\*|null|{rfc9110.URI_reference})"
    category = categories.CORS
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_access_control_allow_origin(str(self.value), cast(HttpResponseLinter, self.message))


class AccessControlAllowOriginTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"https://developer.mozilla.org"]
    expected_out = "https://developer.mozilla.org"


class AccessControlAllowOriginStarTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"*"]
    expected_out = "*"


class AccessControlAllowOriginNullTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"null"]
    expected_out = "null"


class AccessControlAllowOriginMatchTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"https://example.com"]
    expected_out = "https://example.com"
    expected_notes = [CORS_ORIGIN_MATCH]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, message.related)
        request.headers.process([(b"Origin", b"https://example.com")])


class AccessControlAllowOriginMismatchTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"https://other.com"]
    expected_out = "https://other.com"
    expected_notes = [CORS_ORIGIN_MISMATCH]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, message.related)
        request.headers.process([(b"Origin", b"https://example.com")])


class AccessControlAllowOriginStarContextTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"*"]
    expected_out = "*"
    expected_notes = [CORS_ORIGIN_STAR]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, message.related)
        request.headers.process([(b"Origin", b"https://example.com")])


class AccessControlAllowOriginNullContextTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"null"]
    expected_out = "null"
    expected_notes = [CORS_ORIGIN_NULL]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = cast(HttpRequestLinter, message.related)
        request.headers.process([(b"Origin", b"https://example.com")])
