from typing import Optional, Tuple

from httplint.field import FIELD_DEPRECATED
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import unquote_string
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
)


class keep_alive(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Keep-Alive"
    description = """\
The `Keep-Alive` header is completely optional; it is defined primarily because the `keep-alive`
connection token implies that such a header exists, not because anyone actually uses it.

Some implementations (e.g., [Apache](http://httpd.apache.org/)) do generate a `Keep-Alive` header
to convey how many requests they're willing to serve on a single connection, what the connection
timeout is and other information. However, this isn't usually used by clients.

It's safe to remove this header if you wish to save a few bytes."""
    reference = "https://www.rfc-editor.org/rfc/rfc2068.html#section-19.7.1"
    syntax = rfc9110.list_rule(rfc9110.parameter)
    deprecated = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, Optional[str]]:
        try:
            attr, attr_val = field_value.split("=", 1)
            attr_val = unquote_string(attr_val)
        except ValueError:
            attr = field_value
            attr_val = None
        return (attr.lower(), attr_val)


class KeepAliveTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Keep-Alive"
    inputs = [b"timeout=30"]
    expected_out = [("timeout", "30")]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED]


class EmptyKeepAliveTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Keep-Alive"
    inputs = [b""]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED]
