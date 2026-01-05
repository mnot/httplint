from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class proxy_authorization(SingletonField):
    canonical_name = "Proxy-Authorization"
    description = """\
The `Proxy-Authorization` header field allows a user agent to authenticate itself with a proxy
-- usually, but not necessarily, after receiving a 407 (Proxy Authentication Required) response."""
    reference = f"{rfc9110.SPEC_URL}#field.proxy-authorization"
    syntax = rfc9110.Proxy_Authorization
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ProxyAuthorizationTest(FieldTest):
    name = "Proxy-Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="]
    expected_out = "Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="
