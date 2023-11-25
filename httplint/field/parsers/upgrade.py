from httplint.field import HttpField
from httplint.syntax import rfc7230


class upgrade(HttpField):
    canonical_name = "Upgrade"
    description = """\
The `Upgrade` header allows the client to specify what additional communication
protocols it supports and would like to use if the server finds it appropriate
to switch protocols. Servers use it to confirm upgrade to a specific
protocol.

`Upgrade` cannot be used in HTTP/2 or HTTP/3.
"""
    reference = f"{rfc7230.SPEC_URL}#header.upgrade"
    syntax = rfc7230.Upgrade
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True
