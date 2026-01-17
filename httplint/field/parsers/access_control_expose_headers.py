from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.note import categories


class access_control_expose_headers(HttpListField):
    canonical_name = "Access-Control-Expose-Headers"
    description = """\
The `Access-Control-Expose-Headers` response header allows a server to indicate which response
headers should be made available to scripts running in the browser, in response to a cross-origin
request."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-expose-headers"
    syntax = rfc9110.token
    category = categories.CORS
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class AccessControlExposeHeadersTest(FieldTest):
    name = "Access-Control-Expose-Headers"
    inputs = [b"Content-Length, Kuma-Revision"]
    expected_out = ["Content-Length", "Kuma-Revision"]
