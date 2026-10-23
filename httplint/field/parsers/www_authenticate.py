from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.challenge_field import ChallengeField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, ResponseLinterProtocol


class www_authenticate(ChallengeField[ResponseLinterProtocol]):
    canonical_name = "WWW-Authenticate"
    description = """\
The `WWW-Authenticate` response header consists of at least one challenge that
indicates the authentication scheme(s) and parameters applicable."""
    reference = f"{rfc9110.SPEC_URL}#field.www-authenticate"
    # Documents the grammar; ChallengeField parses it itself, so nothing matches against this.
    syntax = rfc9110.WWW_Authenticate
    deprecated = False


class WWWAuthenticateTest(FieldTest[ResponseLinterProtocol]):
    name = "WWW-Authenticate"
    inputs = [b'Basic realm="WallyWorld"']
    expected_out = [("basic", {"realm": "WallyWorld"})]
    expected_notes: NoteClassListType = []


class WWWAuthenticateParamsTest(FieldTest[ResponseLinterProtocol]):
    "RFC 7617 Section 2.1 (the issue #235 reproduction)."

    name = "WWW-Authenticate"
    inputs = [b'Basic realm="foo", charset="UTF-8"']
    expected_out = [("basic", {"realm": "foo", "charset": "UTF-8"})]
    expected_notes: NoteClassListType = []


class WWWAuthenticateDigestTest(FieldTest[ResponseLinterProtocol]):
    "RFC 7616 Section 3.9.1."

    name = "WWW-Authenticate"
    inputs = [
        b'Digest realm="http-auth@example.org", qop="auth, auth-int", algorithm=SHA-256, '
        b'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v", '
        b'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
    ]
    expected_out = [
        (
            "digest",
            {
                "realm": "http-auth@example.org",
                "qop": "auth, auth-int",
                "algorithm": "SHA-256",
                "nonce": "7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v",
                "opaque": "FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS",
            },
        )
    ]
    expected_notes: NoteClassListType = []


class WWWAuthenticateMultipleTest(FieldTest[ResponseLinterProtocol]):
    "RFC 9110 Section 11.6.1: several challenges, in one line and across two."

    name = "WWW-Authenticate"
    inputs = [
        b'Newauth realm="apps", type=1, title="Login to \\"apps\\"", Basic realm="simple"',
        b"Negotiate abc==, Bearer",
    ]
    expected_out = [
        ("newauth", {"realm": "apps", "type": "1", "title": 'Login to "apps"'}),
        ("basic", {"realm": "simple"}),
        ("negotiate", "abc=="),
        ("bearer", {}),
    ]
    expected_notes: NoteClassListType = []


class WWWAuthenticateResyncTest(FieldTest[ResponseLinterProtocol]):
    "A syntax error doesn't lose the challenges after it."

    name = "WWW-Authenticate"
    inputs = [b"Basic realm=My Realm, Digest a=b"]
    expected_out = [("basic", {"realm": "My"}), ("digest", {"a": "b"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]
