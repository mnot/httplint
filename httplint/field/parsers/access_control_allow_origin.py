from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110


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
