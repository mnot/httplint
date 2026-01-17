from httplint.field.list_field import HttpListField
from httplint.syntax import rfc9110


class proxy_authenticate(HttpListField):
    canonical_name = "Proxy-Authenticate"
    description = """\
The `Proxy-Authenticate` response header consists of a challenge that indicates the authentication
scheme and parameters applicable to the proxy for this request-target."""
    reference = f"{rfc9110.SPEC_URL}#field.proxy-authenticate"
    syntax = rfc9110.Proxy_Authenticate
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
