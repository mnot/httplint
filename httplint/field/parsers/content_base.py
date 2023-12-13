from httplint.field import HttpField


class content_base(HttpField):
    canonical_name = "Content-Base"
    description = """\
The `Content-Base` header established the base URI of the message. It has been
deprecated, because it was not implemented widely.
"""
    reference = "https://tools.ietf.org/html/rfc2068#section-14.11"
    syntax = False
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True
    no_coverage = True
