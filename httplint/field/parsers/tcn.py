from httplint.field import HttpField


class tcn(HttpField):
    canonical_name = "TCN"
    description = """\
The `TCN` response header is part of an experimental transparent content negotiation scheme. It
is not widely supported in clients.
"""
    reference = "https://tools.ietf.org/html/rfc2295"
    syntax = False
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
