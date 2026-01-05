from typing import Any, cast
from types import SimpleNamespace

from httplint.field import HttpField
from httplint.field.tests import FieldTest, FakeRequestLinter, FakeResponseLinter
from httplint.message import HttpRequestLinter, HttpResponseLinter, HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.field.notes import DICTIONARY_COMPRESSED_MISSING_VARY


class content_encoding(HttpField):
    canonical_name = "Content-Encoding"
    description = """\
The `Content-Encoding` header's value indicates what content codings have
been applied, and thus what decoding mechanisms must be used to obtain the
media-type referenced by the Content-Type header.

Content-Encoding is primarily used to allow a document to be compressed without losing the identity
of its underlying media type; e.g., `gzip` and `deflate`."""
    reference = f"{rfc9110.SPEC_URL}#field.content-encoding"
    syntax = rfc9110.Content_Encoding
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        # check to see if there are any non-gzip encodings, because
        # that's the only one we ask for.
        if isinstance(self.message, HttpResponseLinter) and isinstance(
            self.message.related, HttpRequestLinter
        ):
            accept_encoding = [
                a[0]
                for a in self.message.related.headers.parsed.get("accept-encoding", [])
            ]
            if field_value.lower() not in accept_encoding:
                add_note(ENCODING_UNWANTED, coding=field_value)
        return field_value.lower()

    def post_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> None:
        if not isinstance(message, HttpResponseLinter):
            return

        ce_values = message.headers.parsed.get("content-encoding", [])
        if any(enc in ["dcb", "dcz"] for enc in ce_values):
            if hasattr(message, "caching") and (
                message.caching.store_shared or message.caching.store_private
            ):
                vary_values = message.headers.parsed.get("vary", set())
                if "available-dictionary" not in vary_values:
                    add_note(DICTIONARY_COMPRESSED_MISSING_VARY)


class ENCODING_UNWANTED(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = (
        "This response uses the '%(coding)s' content-coding, but it wasn't requested."
    )
    _text = """\
This response's `Content-Encoding` header indicates it has the `%(coding)s content-coding applied
, but the client didn't indicate support for it in the request.

Normally, clients ask for the encodings they want in the `Accept-Encoding` request header. Using
encodings that the client doesn't explicitly request can lead to interoperability problems."""


class ContentEncodingTest(FieldTest):
    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]


class ContentEncodingCaseTest(FieldTest):
    name = "Content-Encoding"
    inputs = [b"GZip"]
    expected_out = ["gzip"]


class UnwantedContentEncodingTest(FieldTest):
    name = "Content-Encoding"
    inputs = [b"gzip", b"foo"]
    expected_out = ["gzip", "foo"]
    expected_notes = [ENCODING_UNWANTED]

    def set_context(self, message: HttpMessageLinter) -> None:
        request = FakeRequestLinter()
        request.headers.process([(b"accept-encoding", b"gzip")])
        message.related = request


class ContentEncodingMissingVaryTest(FieldTest):
    name = "Content-Encoding"
    inputs = [b"dcb"]
    expected_out = ["dcb"]
    expected_notes = [DICTIONARY_COMPRESSED_MISSING_VARY]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeResponseLinter, message)
        message.caching = cast(
            Any, SimpleNamespace(store_shared=True, store_private=True)
        )
        # Vary missing 'Available-Dictionary'
        message.headers.parsed["vary"] = set()
