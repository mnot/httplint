from httplint.field.singleton_field import SingletonField
from httplint.types import (
    ResponseLinterProtocol,
)


class p3p(SingletonField[ResponseLinterProtocol]):
    canonical_name = "P3P"
    description = """\
The `P3P` response header allows a server to describe its privacy policy in a
machine-readable way. It has been deprecated, because client support was poor.
"""
    reference = "http://www.w3.org/TR/P3P/#syntax_ext"
    syntax = False
    deprecated = True
    no_coverage = True
