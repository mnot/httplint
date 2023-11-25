from httplint.field import HttpField


class x_pad(HttpField):
    canonical_name = "X-Pad"
    description = """\
    The `%(field_name)s` response header is used to "pad" the size of the response's headers.

    Very old versions of the Netscape browser had a bug whereby a response whose headers were exactly
    256 or 257 bytes long, the browser would consider the response invalid.

    Since the affected browsers (specifically, Netscape 2.x, 3.x and 4.0 up to beta 2) are no longer
    widely used, it's safe to omit this header."""
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
