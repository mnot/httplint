from httplint.field.list_field import HttpListField
from httplint.syntax import rfc9110
from httplint.types import AnyMessageLinterProtocol


class trailer(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Trailer"
    description = """\
The `Trailer` header indicates that the given set of headers will be
present in the trailer of the message, after the content."""
    reference = f"{rfc9110.SPEC_URL}#field.trailer"
    syntax = rfc9110.Trailer
    deprecated = False
