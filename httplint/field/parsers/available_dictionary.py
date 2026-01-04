from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class available_dictionary(HttpField):
    canonical_name = "Available-Dictionary"
    description = """\
The `Available-Dictionary` header field is used by a client to indicate that it has a matching
dictionary available for use in compressing the response."""
    reference = "https://www.rfc-editor.org/rfc/rfc9842.html"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False
    structured_field = True
    sf_type = "item"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        # self.value is (item, params) for sf_type="item"
        if not isinstance(self.value[0], bytes):
            add_note(AVAILABLE_DICTIONARY_BAD_TYPE, got=type(self.value[0]).__name__)


class AVAILABLE_DICTIONARY_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Available-Dictionary header has an invalid type."
    _text = """\
The `Available-Dictionary` header value must be a Byte Sequence. Found `%(got)s`."""


class AvailableDictionaryTest(FieldTest):
    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes = []


class AvailableDictionaryBadTypeTest(FieldTest):
    name = "Available-Dictionary"
    inputs = [b'"not-binary"']
    expected_out: tuple[str, dict] = ("not-binary", {})
    expected_notes = [AVAILABLE_DICTIONARY_BAD_TYPE]
