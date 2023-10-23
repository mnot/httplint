from httplint.field import HttpField, RFC6265


class set_cookie2(HttpField):
    canonical_name = "Set-Cookie2"
    description = """\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
    reference = RFC6265
    list_header = True
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
