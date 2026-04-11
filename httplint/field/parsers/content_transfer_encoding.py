from httplint.field.singleton_field import SingletonField
from httplint.types import (
    AnyMessageLinterProtocol,
)


class content_transfer_encoding(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Transfer-Encoding"
    description = """\
The `Content-Transfer-Encoding` isn't part of HTTP, but it is used in MIME protocols in a manner
analogous to `Transfer-Encoding`."""
    reference = "https://www.rfc-editor.org/rfc/rfc2616#section-19.4.5"
    syntax = False
    deprecated = True
    no_coverage = True
