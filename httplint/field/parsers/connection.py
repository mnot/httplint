from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110


class connection(HttpListField):
    canonical_name = "Connection"
    description = """\
The `Connection` header allows senders to specify which headers are hop-by-hop; that is, those that
are not forwarded by intermediaries.

It also indicates options that are desired for this particular connection; e.g., `close` means that
it should not be reused.

Connection is only valid in HTTP/1.x; HTTP/2 and HTTP/3 forbit it."""
    reference = f"{rfc9110.SPEC_URL}#field.connection"
    syntax = rfc9110.Connection
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True


class ConnectionTest(FieldTest):
    name = "Connection"
    inputs = [b"close"]
    expected_out = ["close"]
