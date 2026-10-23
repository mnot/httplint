from typing import Any

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.field.utils import coding_acceptable
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
    SFItemType,
)


class available_dictionary(StructuredField[RequestLinterProtocol]):
    canonical_name = "Available-Dictionary"
    description = """\
The `Available-Dictionary` header field is used by a client to indicate that it has a matching
dictionary available for use in compressing the response."""
    reference = "https://www.rfc-editor.org/rfc/rfc9842.html"
    syntax = False  # Structured Field
    category = categories.CONNEG
    deprecated = False
    sf_type = "item"
    value: SFItemType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        # self.value is (item, params) for sf_type="item"
        if not isinstance(self.value[0], bytes):
            add_note(AVAILABLE_DICTIONARY_BAD_TYPE, got=type(self.value[0]).__name__)

    def post_check(self, add_note: AddNoteMethodType) -> None:
        if self.message.message_type != "request":
            return

        ae_values = self.message.headers.parsed.get("accept-encoding", [])
        # RFC 9842 Section 6.1: the client lists the encodings it supports; a `*` doesn't count.
        if not any(coding_acceptable(ae_values, enc, wildcard=False) for enc in ("dcb", "dcz")):
            add_note(AVAILABLE_DICTIONARY_MISSING_AE)


class AVAILABLE_DICTIONARY_MISSING_AE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "This request advertises a dictionary for compression, but the client doesn't support it."
    )
    _text = """\
The `Available-Dictionary` header is present, but `Accept-Encoding` does not list 'dcb' or 'dcz'
as acceptable: it leaves them out, or gives them a `q` value of 0.

[RFC 9842 Section 6.1](https://www.rfc-editor.org/rfc/rfc9842.html#section-6.1) requires that if a
client sends `Available-Dictionary`, it MUST also advertise support for dictionary-based content
encoding (dcb or dcz) in `Accept-Encoding`."""


class AVAILABLE_DICTIONARY_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Available-Dictionary header has an invalid type."
    _text = """\
The `Available-Dictionary` header value must be a Byte Sequence. Found `%(got)s`."""


class AvailableDictionaryTest(FieldTest[RequestLinterProtocol]):
    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = []

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.parsed["accept-encoding"] = [("dcb", {})]


class AvailableDictionaryBadTypeTest(FieldTest[RequestLinterProtocol]):
    name = "Available-Dictionary"
    inputs = [b'"not-binary"']
    expected_out: tuple[str, dict[str, Any]] = ("not-binary", {})
    expected_notes: NoteClassListType = [AVAILABLE_DICTIONARY_BAD_TYPE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.parsed["accept-encoding"] = [("dcb", {})]


class AvailableDictionaryMissingAETest(FieldTest[RequestLinterProtocol]):
    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = [AVAILABLE_DICTIONARY_MISSING_AE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        # Accept-Encoding missing 'dcb' or 'dcz'
        message.headers.parsed["accept-encoding"] = [("gzip", {})]


class AvailableDictionaryQZeroTest(FieldTest[RequestLinterProtocol]):
    "dcb;q=0 refuses dictionary compression, so it isn't support."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = [AVAILABLE_DICTIONARY_MISSING_AE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"gzip, dcb;q=0, dcz;q=0")])


class AvailableDictionaryOneQZeroTest(FieldTest[RequestLinterProtocol]):
    "Guard: one of dcb and dcz is enough; main also accepts this."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = []

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"dcb;q=0, dcz;q=0.5")])


class AvailableDictionaryWildcardTest(FieldTest[RequestLinterProtocol]):
    "Guard: `*` doesn't advertise dictionary-aware encodings (RFC 9842 Section 6.1)."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = [AVAILABLE_DICTIONARY_MISSING_AE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"*")])


class AvailableDictionaryCaseTest(FieldTest[RequestLinterProtocol]):
    "Guard: Accept-Encoding is parsed to lower case; main also accepts this."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = []

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"gzip, DCB;q=0.8")])


class AvailableDictionaryWildcardQZeroTest(FieldTest[RequestLinterProtocol]):
    "`*` doesn't make up for an explicit refusal of dcb (dcz isn't listed)."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = [AVAILABLE_DICTIONARY_MISSING_AE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"*, dcb;q=0")])


class AvailableDictionaryDczOnlyTest(FieldTest[RequestLinterProtocol]):
    "Guard: dcz alone is support; main also accepts this."

    name = "Available-Dictionary"
    inputs = [b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"]
    expected_out: tuple[bytes, dict[str, Any]] = (
        b"\xa5\x91\xa6\xd4\x0b\xf4 @J\x01\x173\xcf\xb7\xb1\x90\xd6,e\xbf\x0b\xcd\xa3"
        b"+W\xb2w\xd9\xad\x9f\x14n",
        {},
    )
    expected_notes: NoteClassListType = []

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.headers.process([(b"accept-encoding", b"dcz")])
