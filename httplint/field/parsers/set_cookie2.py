from httplint.field import HttpField
from httplint.field import RFC6265


class set_cookie2(HttpField):
    canonical_name = "Set-Cookie2"
    description = """\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
    reference = RFC6265
    syntax = False
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
