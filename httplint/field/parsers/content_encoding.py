from types import SimpleNamespace
from typing import cast

from httplint.field.list_field import HttpListField
from httplint.field.tests import FakeRequestLinter, FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    CachingProtocol,
    LinterProtocol,
    NoteClassListType,
    ResponseLinterProtocol,
)


class content_encoding(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Encoding"
    description = """\
The `Content-Encoding` header's value indicates what content codings have
been applied, and thus what decoding mechanisms must be used to obtain the
media-type referenced by the Content-Type header.

Content-Encoding is primarily used to allow a document to be compressed without losing the identity
of its underlying media type; e.g., `gzip` and `deflate`."""
    reference = f"{rfc9110.SPEC_URL}#field.content-encoding"
    syntax = rfc9110.Content_Encoding
    category = categories.CONNEG
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        # check to see if there are any non-gzip encodings, because
        # that's the only one we ask for.
        if (
            (response := self.message.as_response)
            and response.request
            and response.request.message_type == "request"
        ):
            accept_encoding = [
                a[0] for a in response.request.headers.parsed.get("accept-encoding", [])
            ]
            if field_value.lower() not in accept_encoding:
                add_note(ENCODING_UNWANTED, coding=field_value)
        return field_value.lower()

    def post_check(self, message: LinterProtocol, add_note: AddNoteMethodType) -> None:
        if not message.as_response:
            return

        ce_values = message.headers.parsed.get("content-encoding", [])
        if any(enc in ["dcb", "dcz"] for enc in ce_values):
            if hasattr(message, "caching") and (
                message.caching.store_shared or message.caching.store_private
            ):
                vary_values = message.headers.parsed.get("vary", set())
                if "available-dictionary" not in vary_values:
                    add_note(DICTIONARY_COMPRESSED_MISSING_VARY)


class DICTIONARY_COMPRESSED_MISSING_VARY(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = (
        "This response is compressed with a dictionary,"
        "but is missing Vary: Available-Dictionary."
    )
    _text = """\
The response is compressed with a dictionary (dcb or dcz) and is cacheable, but does not list
`Available-Dictionary` in the `Vary` header.

[RFC 9842 Section 6.2](https://www.rfc-editor.org/rfc/rfc9842.html#section-6.2) requires that
cacheable dictionary-compressed responses MUST include `Available-Dictionary` in the `Vary` header
to prevent serving compressed content to clients that do not have the dictionary."""


class ENCODING_UNWANTED(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "This response uses the '%(coding)s' content-coding, but it wasn't requested."
    _text = """\
This response's `Content-Encoding` header indicates it has the `%(coding)s content-coding applied
, but the client didn't indicate support for it in the request.

Normally, clients ask for the encodings they want in the `Accept-Encoding` request header. Using
encodings that the client doesn't explicitly request can lead to interoperability problems."""


class ContentEncodingTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip")])


class ContentEncodingCaseTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"GZip"]
    expected_out = ["gzip"]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip")])


class ContentEncodingUnwantedTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"gzip, foo"]
    expected_out = ["gzip", "foo"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        request = FakeRequestLinter()
        request.headers.process([(b"accept-encoding", b"gzip")])
        message.request = request


class DictionaryCompressedMissingVaryTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"dcb"]
    expected_out = ["dcb"]
    expected_notes: NoteClassListType = [DICTIONARY_COMPRESSED_MISSING_VARY]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"dcb")])
        message.caching = cast(
            CachingProtocol, SimpleNamespace(store_shared=True, store_private=True)
        )
        # Vary missing 'Available-Dictionary'
        message.headers.parsed["vary"] = set()
