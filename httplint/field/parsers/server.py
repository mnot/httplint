from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110


class server(HttpField):
    canonical_name = "Server"
    description = """\
The `Server` response header contains information about the software used by the origin server to
handle the request."""
    reference = f"{rfc9110.SPEC_URL}#field.server"
    syntax = rfc9110.Server
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class ServerTest(FieldTest):
    name = "Server"
    inputs = [b"Apache/2.4.1 (Unix)", b"CERN/3.0 libwww/2.17"]
    expected_out = ["Apache/2.4.1 (Unix)", "CERN/3.0 libwww/2.17"]
    expected_notes = []
