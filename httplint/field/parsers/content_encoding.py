from httplint.field import HttpField
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.message import HttpRequestLinter, HttpResponseLinter, HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


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
    list_header = True
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
