from httplint.field import RFC6265
from httplint.field.list_field import HttpListField
from httplint.note import categories
from httplint.types import ResponseLinterProtocol


class set_cookie2(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Set-Cookie2"
    description = """\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
    reference = RFC6265
    syntax = False
    category = categories.COOKIES
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
