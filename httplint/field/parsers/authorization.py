from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.challenge_field import CredentialsField
from httplint.field.singleton_field import SINGLE_HEADER_REPEAT
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
)


class authorization(CredentialsField[RequestLinterProtocol]):
    canonical_name = "Authorization"
    description = """\
The `Authorization` header field allows a user agent to authenticate itself with an origin server
-- usually, but not necessarily, after receiving a 401 (Unauthorized) response."""
    reference = f"{rfc9110.SPEC_URL}#field.authorization"
    # Documents the grammar; CredentialsField parses it itself, so nothing matches against this.
    syntax = rfc9110.Authorization
    category = categories.SECURITY
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AuthorizationTest(FieldTest[RequestLinterProtocol]):
    "RFC 7617 Section 2: token68."

    name = "Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="]
    expected_out = ("basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")


class AuthorizationDigestTest(FieldTest[RequestLinterProtocol]):
    "RFC 7616 Section 3.9.1."

    name = "Authorization"
    inputs = [
        b'Digest username="Mufasa", realm="http-auth@example.org", '
        b'uri="/dir/index.html", algorithm=MD5, nc=00000001, '
        b'cnonce="f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ", '
        b'qop=auth, response="8ca523f5e9506fed4657c9700eebdbec", '
        b'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
    ]
    expected_out = (
        "digest",
        {
            "username": "Mufasa",
            "realm": "http-auth@example.org",
            "uri": "/dir/index.html",
            "algorithm": "MD5",
            "nc": "00000001",
            "cnonce": "f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ",
            "qop": "auth",
            "response": "8ca523f5e9506fed4657c9700eebdbec",
            "opaque": "FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS",
        },
    )


class AuthorizationRepeatTest(FieldTest[RequestLinterProtocol]):
    name = "Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==", b"Basic Zm9vOmJhcg=="]
    expected_out = ("basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")
    expected_notes: NoteClassListType = [SINGLE_HEADER_REPEAT]


class AuthorizationSecondSchemeTest(FieldTest[RequestLinterProtocol]):
    "Credentials are a single challenge-shaped element."

    name = "Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==, Digest username=foo"]
    expected_out = ("basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class AuthorizationEmptyTest(FieldTest[RequestLinterProtocol]):
    "Credentials aren't a list: an empty value is a syntax error."

    name = "Authorization"
    inputs = [b""]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class AuthorizationLeadingCommaTest(FieldTest[RequestLinterProtocol]):
    name = "Authorization"
    inputs = [b", Basic abc"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class AuthorizationOnlyCommaTest(FieldTest[RequestLinterProtocol]):
    name = "Authorization"
    inputs = [b","]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class AuthorizationTrailingCommaTest(FieldTest[RequestLinterProtocol]):
    name = "Authorization"
    inputs = [b"Basic abc,"]
    expected_out = ("basic", "abc")
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]


class AuthorizationTrailingJunkTest(FieldTest[RequestLinterProtocol]):
    name = "Authorization"
    inputs = [b"Basic abc extra"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]
