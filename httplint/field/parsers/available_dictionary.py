from typing import TYPE_CHECKING, cast

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType
from httplint.message import HttpRequestLinter
from httplint.field.notes import AVAILABLE_DICTIONARY_MISSING_AE

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class available_dictionary(StructuredField):
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
    sf_type = "item"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        # self.value is (item, params) for sf_type="item"
        if not isinstance(self.value[0], bytes):
            add_note(AVAILABLE_DICTIONARY_BAD_TYPE, got=type(self.value[0]).__name__)

    def post_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> None:
        if not isinstance(message, HttpRequestLinter):
            return

        ae_values = message.headers.parsed.get("accept-encoding", [])
        has_dictionary_support = False
        for enc, _params in ae_values:
            if enc in ["dcb", "dcz"]:
                has_dictionary_support = True
                break
        if not has_dictionary_support:
            add_note(AVAILABLE_DICTIONARY_MISSING_AE)


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

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeRequestLinter, message)
        message.headers.parsed["accept-encoding"] = [("dcb", {})]


class AvailableDictionaryBadTypeTest(FieldTest):
    name = "Available-Dictionary"
    inputs = [b'"not-binary"']
    expected_out: tuple[str, dict] = ("not-binary", {})
    expected_notes = [AVAILABLE_DICTIONARY_BAD_TYPE]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeRequestLinter, message)
        message.headers.parsed["accept-encoding"] = [("dcb", {})]


class AvailableDictionaryMissingAETest(FieldTest):
    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes = [AVAILABLE_DICTIONARY_MISSING_AE]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeRequestLinter, message)
        # Accept-Encoding missing 'dcb' or 'dcz'
        message.headers.parsed["accept-encoding"] = [("gzip", {})]
