from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.challenge_field import ChallengeField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, ResponseLinterProtocol


class proxy_authenticate(ChallengeField[ResponseLinterProtocol]):
    canonical_name = "Proxy-Authenticate"
    description = """\
The `Proxy-Authenticate` response header consists of a challenge that indicates the authentication
scheme and parameters applicable to the proxy for this request-target."""
    reference = f"{rfc9110.SPEC_URL}#field.proxy-authenticate"
    # Documents the grammar; ChallengeField parses it itself, so nothing matches against this.
    syntax = rfc9110.Proxy_Authenticate
    deprecated = False


class ProxyAuthenticateTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Authenticate"
    inputs = [b'Basic realm="proxy", charset="UTF-8"']
    expected_out = [("Basic", {"realm": "proxy", "charset": "UTF-8"})]
    expected_notes: NoteClassListType = []


class ProxyAuthenticateBadSyntaxTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Authenticate"
    inputs = [b'Basic realm="proxy" charset="UTF-8"']
    expected_out = [("Basic", {"realm": "proxy"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX_DETAILED]
