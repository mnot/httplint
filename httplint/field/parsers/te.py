from httplint.field import HttpField
from httplint.syntax import rfc7230


class te(HttpField):
    canonical_name = "TE"
    description = """\
The `TE` request header indicates what HTTP/1.1 transfer-codings the client is willing to accept in
the response. Additionally, if it contains the special value `trailers` it indicates that the sender is willing to accept trailer fields after the content.

The most common transfer-coding, `chunked`, doesn't need to be listed in `TE`.

`TE` can only be used with the value `trailers` in HTTP/2 and HTTP/3.
"""
    reference = f"{rfc7230.SPEC_URL}#header.te"
    syntax = rfc7230.TE
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True
