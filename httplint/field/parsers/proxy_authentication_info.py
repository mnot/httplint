from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class proxy_authentication_info(HttpField):
    canonical_name = "Proxy-Authentication-Info"
    description = """\
The `Proxy-Authentication-Info` header field is used to communicate information after
the client's authentication credentials have been accepted by a proxy."""
    reference = f"{rfc9110.SPEC_URL}#field.proxy-authentication-info"
    syntax = rfc9110.Proxy_Authentication_Info
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ProxyAuthenticationInfoTest(FieldTest):
    name = "Proxy-Authentication-Info"
    inputs = [
        b'nextnonce="5Yg8-VL198_7ulNinj-Vfs4567-32n3-84333", '
        b'qop="auth", '
        b'rspauth="6629fae49393a05397450978507c4ef1", '
        b'cnonce="0a4f113b", '
        b"nc=00000002"
    ]
    expected_out = [
        'nextnonce="5Yg8-VL198_7ulNinj-Vfs4567-32n3-84333"',
        'qop="auth"',
        'rspauth="6629fae49393a05397450978507c4ef1"',
        'cnonce="0a4f113b"',
        "nc=00000002",
    ]
