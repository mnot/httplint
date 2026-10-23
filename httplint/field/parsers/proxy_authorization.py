from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.challenge_field import CredentialsField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


class proxy_authorization(CredentialsField[RequestLinterProtocol]):
    canonical_name = "Proxy-Authorization"
    description = """\
The `Proxy-Authorization` header field allows a user agent to authenticate itself with a proxy
-- usually, but not necessarily, after receiving a 407 (Proxy Authentication Required) response."""
    reference = f"{rfc9110.SPEC_URL}#field.proxy-authorization"
    # Documents the grammar; CredentialsField parses it itself, so nothing matches against this.
    syntax = rfc9110.Proxy_Authorization
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ProxyAuthorizationTest(FieldTest[RequestLinterProtocol]):
    name = "Proxy-Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="]
    expected_out = ("Basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")


class ProxyAuthorizationEmptyTest(FieldTest[RequestLinterProtocol]):
    "Credentials aren't a list: an empty value is a syntax error."

    name = "Proxy-Authorization"
    inputs = [b""]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class ProxyAuthorizationLeadingCommaTest(FieldTest[RequestLinterProtocol]):
    name = "Proxy-Authorization"
    inputs = [b", Basic abc"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class ProxyAuthorizationTrailingCommaTest(FieldTest[RequestLinterProtocol]):
    name = "Proxy-Authorization"
    inputs = [b"Basic abc,"]
    expected_out = ("Basic", "abc")
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]
