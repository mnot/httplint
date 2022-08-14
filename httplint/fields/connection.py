from httplint.fields import HttpField
from httplint.fields._test import FieldTest
from httplint.syntax import rfc7230


class connection(HttpField):
    canonical_name = "Connection"
    description = """\
The `Connection` header allows senders to specify which headers are hop-by-hop; that is, those that
are not forwarded by intermediaries.

It also indicates options that are desired for this particular connection; e.g., `close` means that
it should not be reused."""
    reference = f"{rfc7230.SPEC_URL}#header.connection"
    syntax = rfc7230.Connection
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True


class ConnectionTest(FieldTest):
    name = "Connection"
    inputs = [b"close"]
    expected_out = ["close"]
