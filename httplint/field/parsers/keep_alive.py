from typing import Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7230, rfc7231
from httplint.types import AddNoteMethodType
from httplint.field.utils import unquote_string
from httplint.field.notes import FIELD_DEPRECATED


class keep_alive(HttpField):
    canonical_name = "Keep-Alive"
    description = """\
The `Keep-Alive` header is completely optional; it is defined primarily because the `keep-alive`
connection token implies that such a header exists, not because anyone actually uses it.

Some implementations (e.g., [Apache](http://httpd.apache.org/)) do generate a `Keep-Alive` header
to convey how many requests they're willing to serve on a single connection, what the connection
timeout is and other information. However, this isn't usually used by clients.

It's safe to remove this header if you wish to save a few bytes."""
    reference = "https://tools.ietf.org/html/rfc2068#section-19.7.1"
    syntax = rfc7230.list_rule(rfc7231.parameter)
    list_header = True
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, str]:
        try:
            attr, attr_val = field_value.split("=", 1)
            attr_val = unquote_string(attr_val)
        except ValueError:
            attr = field_value
            attr_val = None
        return (attr.lower(), attr_val)


class KeepAliveTest(FieldTest):
    name = "Keep-Alive"
    inputs = [b"timeout=30"]
    expected_out = [("timeout", "30")]
    expected_notes = [FIELD_DEPRECATED]


class EmptyKeepAliveTest(FieldTest):
    name = "Keep-Alive"
    inputs = [b""]
    expected_notes = [FIELD_DEPRECATED]
