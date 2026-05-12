from httplint.field.singleton_field import SingletonField
from httplint.types import (
    AnyMessageLinterProtocol,
)


class content_base(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Base"
    description = """\
The `Content-Base` header established the base URI of the message. It has been
deprecated, because it was not implemented widely.
"""
    reference = "https://www.rfc-editor.org/rfc/rfc2068#section-14.11"
    syntax = False
    deprecated = True
    no_coverage = True
