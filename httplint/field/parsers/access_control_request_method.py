from httplint.field.cors import CORS_PREFLIGHT_REQUEST
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, RequestLinterProtocol


class access_control_request_method(SingletonField):
    canonical_name = "Access-Control-Request-Method"
    description = """\
The `Access-Control-Request-Method` request header is used by browsers when issuing a CORS
preflight request, to let the server know which HTTP method will be used when the actual request
is made."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-request-method"
    syntax = rfc9110.token
    category = categories.CORS
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False


class AccessControlRequestMethodTest(FieldTest):
    name = "Access-Control-Request-Method"
    inputs = [b"POST"]
    expected_out = "POST"
    expected_notes: NoteClassListType = [CORS_PREFLIGHT_REQUEST]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.method = "OPTIONS"
        # Manually populate parsed headers to avoid triggering notes on context headers
        message.headers.parsed["origin"] = "http://example.com"
