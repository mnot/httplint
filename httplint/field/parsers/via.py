from functools import partial

from httplint.field.list_field import HttpListField
from httplint.field.list_split import split_list_field
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
)


class via(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Via"
    description = """\
The `Via` header is added to requests and responses by proxies and other HTTP intermediaries. It
can be used to help avoid request loops and identify the protocol capabilities of all senders along
the request/response chain."""
    reference = f"{rfc9110.SPEC_URL}#field.via"
    syntax = rfc9110.Via
    deprecated = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        # Same as the base class, except that commas inside a comment don't split.
        for value in split_list_field(field_value, comments=True):
            offset_add_note = partial(
                self.message.notes.add,
                f"offset-{offset}",
                field_name=self.canonical_name,
            )
            try:
                with self._syntax_checked(value, offset_add_note):
                    parsed_value = self.parse(value.strip(), offset_add_note)
            except ValueError:
                continue
            self.value.append(parsed_value)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        via_list = "<ul>" + "\n".join([f"<li><code>{v}</code></li>" for v in self.value]) + "</ul>"
        add_note(VIA_PRESENT, via_list=via_list)


class VIA_PRESENT(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "One or more intermediaries are present."
    _text = """\
The `Via` header indicates that one or more intermediaries are present between the user agent and
the origin server for the resource.

This may indicate that a proxy is configured, or that the server uses a "reverse proxy" or CDN in
front of it.

There field has three space-separated components; first, the HTTP version of the message that the
intermediary received, then the identity of the intermediary (usually but not always its hostname),
and then optionally a product identifier or comment (usually used to identify the software being
used)."""


class ViaTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Via"
    inputs = [b"1.1 test"]
    expected_out = ["1.1 test"]
    expected_notes: NoteClassListType = [VIA_PRESENT]


class ViaCommentCommaTest(FieldTest[AnyMessageLinterProtocol]):
    "A comma inside a comment doesn't split the value."

    name = "Via"
    inputs = [b"1.1 a, 1.1 b (comment, with comma)"]
    expected_out = ["1.1 a", "1.1 b (comment, with comma)"]
    expected_notes: NoteClassListType = [VIA_PRESENT]


class ViaNestedCommentTest(FieldTest[AnyMessageLinterProtocol]):
    "Comments nested to the three levels the syntax rule allows stay in one value."

    name = "Via"
    inputs = [b"1.1 a (x (y, z (w, v))), 1.0 b"]
    expected_out = ["1.1 a (x (y, z (w, v)))", "1.0 b"]
    expected_notes: NoteClassListType = [VIA_PRESENT]
