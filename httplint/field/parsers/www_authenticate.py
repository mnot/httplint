from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110


class www_authenticate(HttpField):
    canonical_name = "WWW-Authenticate"
    description = """\
The `WWW-Authenticate` response header consists of at least one challenge that
indicates the authentication scheme(s) and parameters applicable."""
    reference = f"{rfc9110.SPEC_URL}#field.www-authenticate"
    syntax = rfc9110.WWW_Authenticate
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class WWWAuthenticateTest(FieldTest):
    name = "WWW-Authenticate"
    inputs = [b'Basic realm="WallyWorld"']
    expected_out = ['Basic realm="WallyWorld"']
    expected_notes = []
