from types import SimpleNamespace
from typing import cast

from httplint.field.codings import (
    CODING_ALIAS_DEPRECATED,
    coding_acceptable,
    note_deprecated_codings,
)
from httplint.field.list_field import HttpListField
from httplint.field.tests import FakeRequestLinter, FieldTest
from httplint.field.utils import vary_covers
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    CachingProtocol,
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
        coding = field_value.lower()
        if (
            coding not in ("", "identity")
            and (response := self.message.as_response)
            and response.request
            and response.request.message_type == "request"
        ):
            accept_encoding = response.request.headers.parsed.get("accept-encoding")
            if accept_encoding is not None and not coding_acceptable(accept_encoding, coding):
                add_note(ENCODING_UNWANTED, coding=field_value)
        return coding

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        note_deprecated_codings(self.value, add_note, self.category)

    def post_check(self, add_note: AddNoteMethodType) -> None:
        if not self.message.as_response:
            return

        ce_values = self.message.headers.parsed.get("content-encoding", [])
        if any(enc in ["dcb", "dcz"] for enc in ce_values):
            if hasattr(self.message, "caching") and (
                self.message.caching.store_shared or self.message.caching.store_private
            ):
                if not vary_covers(self.message, "available-dictionary"):
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
This response's `Content-Encoding` header indicates it has the `%(coding)s` content-coding
applied, but the client didn't ask for it in the request: either it didn't list the coding
(or `*`) in `Accept-Encoding`, or it gave the coding a `q` value of 0 to refuse it.

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


class ContentEncodingNoAcceptEncodingTest(FieldTest[AnyMessageLinterProtocol]):
    "A request without Accept-Encoding accepts any coding."

    name = "Content-Encoding"
    inputs = [b"gzip, br"]
    expected_out = ["gzip", "br"]
    expected_notes: NoteClassListType = []


class ContentEncodingWildcardTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"*")])


class ContentEncodingQZeroTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=0, br")])


class ContentEncodingWildcardQZeroTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: main also flags this."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"br, *;q=0")])


class ContentEncodingExplicitOverridesWildcardTest(FieldTest[AnyMessageLinterProtocol]):
    "gzip is refused explicitly, br is allowed by the wildcard (main flags br)."

    name = "Content-Encoding"
    inputs = [b"br"]
    expected_out = ["br"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=0, *;q=0.5")])


class ContentEncodingExplicitRefusalOverridesWildcardTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: main also flags this."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=0, *;q=0.5")])


class ContentEncodingInvalidQTest(FieldTest[AnyMessageLinterProtocol]):
    "An invalid q on an Accept-Encoding entry (already a syntax problem) counts as q=1."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=abc")])


class ContentEncodingEmptyAcceptEncodingTest(FieldTest[AnyMessageLinterProtocol]):
    "An empty Accept-Encoding means that only identity is acceptable."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"")])
        assert message.request.headers.parsed["accept-encoding"] == []


class ContentEncodingEmptyAcceptEncodingIdentityTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: main also accepts this."

    name = "Content-Encoding"
    inputs = [b"identity"]
    expected_out = ["identity"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"")])


class ContentEncodingIdentityTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"identity"]
    expected_out = ["identity"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip")])


class DictionaryCompressedVaryStarTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"dcb"]
    expected_out = ["dcb"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"dcb")])
        message.caching = cast(
            CachingProtocol, SimpleNamespace(store_shared=True, store_private=True)
        )
        message.headers.parsed["vary"] = ["*"]


class DictionaryCompressedVaryCoveredTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"dcb"]
    expected_out = ["dcb"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"dcb")])
        message.caching = cast(
            CachingProtocol, SimpleNamespace(store_shared=True, store_private=True)
        )
        message.headers.parsed["vary"] = ["accept-encoding", "available-dictionary"]


class ContentEncodingXGzipTest(FieldTest[AnyMessageLinterProtocol]):
    "x-gzip is equivalent to gzip (RFC 9110 Section 8.4.1.3)."

    name = "Content-Encoding"
    inputs = [b"x-gzip"]
    expected_out = ["x-gzip"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip")])


class ContentEncodingXGzipRequestTest(FieldTest[AnyMessageLinterProtocol]):
    "The alias works the other way too: gzip is acceptable when the request lists x-gzip."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip")])


class ContentEncodingXGzipQZeroTest(FieldTest[AnyMessageLinterProtocol]):
    "A q=0 on gzip refuses x-gzip as well, even though a wildcard would otherwise allow it."

    name = "Content-Encoding"
    inputs = [b"x-gzip"]
    expected_out = ["x-gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED, CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=0, *;q=1")])


class ContentEncodingXCompressTest(FieldTest[AnyMessageLinterProtocol]):
    "x-compress is equivalent to compress (RFC 9110 Section 8.4.1.1)."

    name = "Content-Encoding"
    inputs = [b"x-compress"]
    expected_out = ["x-compress"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"compress")])


class ContentEncodingXGzipNotCompressTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: the aliases don't cross over; x-gzip is not acceptable to a client that lists compress."

    name = "Content-Encoding"
    inputs = [b"x-gzip"]
    expected_out = ["x-gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED, CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"compress")])


class ContentEncodingExactBeforeAliasTest(FieldTest[AnyMessageLinterProtocol]):
    "An entry for the coding itself decides, even if an earlier entry refuses its alias."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip;q=0, gzip")])


class ContentEncodingExactAliasBeforeAliasTest(FieldTest[AnyMessageLinterProtocol]):
    "As above, for x-gzip with an earlier gzip;q=0."

    name = "Content-Encoding"
    inputs = [b"x-gzip"]
    expected_out = ["x-gzip"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"gzip;q=0, x-gzip")])


class ContentEncodingExactCompressBeforeAliasTest(FieldTest[AnyMessageLinterProtocol]):
    "As above, for x-compress with an earlier compress;q=0."

    name = "Content-Encoding"
    inputs = [b"x-compress"]
    expected_out = ["x-compress"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"compress;q=0, x-compress")])


class ContentEncodingExactRefusalBeforeAliasTest(FieldTest[AnyMessageLinterProtocol]):
    "An exact q=0 beats an alias that is allowed (main flags this too)."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip, gzip;q=0")])


class ContentEncodingAliasChainTest(FieldTest[AnyMessageLinterProtocol]):
    "In a chain, each coding is checked on its own: only br is unwanted."

    name = "Content-Encoding"
    inputs = [b"gzip, br"]
    expected_out = ["gzip", "br"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip;q=0, gzip")])


class ContentEncodingRepeatedCodingTest(FieldTest[AnyMessageLinterProtocol]):
    "A coding that repeats in the chain is acceptable each time."

    name = "Content-Encoding"
    inputs = [b"gzip, gzip"]
    expected_out = ["gzip", "gzip"]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip;q=0, gzip")])


class ContentEncodingAliasRefusalOverridesWildcardTest(FieldTest[AnyMessageLinterProtocol]):
    "With no entry for the coding itself, a refused alias beats the wildcard."

    name = "Content-Encoding"
    inputs = [b"gzip"]
    expected_out = ["gzip"]
    expected_notes: NoteClassListType = [ENCODING_UNWANTED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        assert message.request is not None
        message.request.headers.process([(b"accept-encoding", b"x-gzip;q=0, *")])


class ContentEncodingXGzipDeprecatedTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"X-Gzip"]
    expected_out = ["x-gzip"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]


class ContentEncodingXGzipInChainTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Encoding"
    inputs = [b"gzip, x-gzip"]
    expected_out = ["gzip", "x-gzip"]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]


class ContentEncodingStandardCodingsTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: gzip and compress don't get the deprecated-alias note."

    name = "Content-Encoding"
    inputs = [b"gzip, compress"]
    expected_out = ["gzip", "compress"]
    expected_notes: NoteClassListType = []
