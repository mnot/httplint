from typing import TYPE_CHECKING, cast, Any
from types import SimpleNamespace

from http_sf import Token
from httplint.field import HttpField
from httplint.field.tests import FieldTest, FakeResponseLinter, FakeRequestLinter
from httplint.note import Note, categories, levels
from httplint.field.notes import BAD_SYNTAX
from httplint.types import AddNoteMethodType
from httplint.message import HttpResponseLinter, HttpRequestLinter

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class accept_ch(HttpField):
    canonical_name = "Accept-CH"
    description = """\
The `Accept-CH` response header field allows servers to indicate that they are
willing to process the specified Client Hints."""
    reference = "https://www.rfc-editor.org/rfc/rfc8942.html#section-3.1"
    syntax = False  # SF
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "list"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.message or not isinstance(self.message, HttpResponseLinter):
            return

        # Warn if the request URI scheme is http
        request = self.message.related
        if request and isinstance(request, HttpRequestLinter) and request.uri:
            if request.uri.lower().startswith("http:"):
                add_note(ACCEPT_CH_IN_PLAIN_HTTP)

        # Check for valid syntax (must be Tokens)
        for item in self.value:
            if not isinstance(item[0], Token):
                add_note(
                    BAD_SYNTAX,
                    ref_uri=self.reference,
                )
                return

    def post_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> None:
        if not isinstance(message, HttpResponseLinter):
            return

        # Check if every field name in Accept-CH is also present in the Vary header
        # if the response is cacheable.
        if hasattr(message, "caching") and (
            message.caching.store_shared or message.caching.store_private
        ):
            vary_header = message.headers.parsed.get("vary", [])
            missing_vary = []
            for item in self.value:
                # item is (value, params)
                field_name = item[0]
                if field_name not in vary_header:
                    missing_vary.append(str(field_name))

            if missing_vary:
                add_note(
                    ACCEPT_CH_MISSING_VARY,
                    missing_fields=", ".join(missing_vary),
                )


class ACCEPT_CH_IN_PLAIN_HTTP(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Accept-CH is ignored over plain HTTP."
    _text = """\
The `Accept-CH` header field should only be used on secure (HTTPS) responses. Using it over plain
HTTP exposes the user's information to network observers. Because of this, browsers will ignore the
header."""


class ACCEPT_CH_MISSING_VARY(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Accept-CH lists fields that are missing from Vary."
    _text = """\
The following fields appear in `Accept-CH` but are not listed in the `Vary` header:
%(missing_fields)s.

Because these fields can affect the response content, they should be included in `Vary` to ensure
that caches store separate responses for different client hints."""


class AcceptCHTest(FieldTest):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example, Sec-CH-Example-2"]
    expected_out = [(Token("Sec-CH-Example"), {}), (Token("Sec-CH-Example-2"), {})]
    expected_notes = []


class AcceptCHBadSyntaxTest(FieldTest):
    name = "Accept-CH"
    inputs = [b'"foo"']
    expected_out = [("foo", {})]
    expected_notes = [
        BAD_SYNTAX,
    ]


class AcceptCHHTTPTest(FieldTest):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example"]
    expected_out = [(Token("Sec-CH-Example"), {})]
    expected_notes = [ACCEPT_CH_IN_PLAIN_HTTP]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeResponseLinter, message)
        message.related = FakeRequestLinter()
        message.related.uri = "http://example.com/"


class AcceptCHMissingVaryTest(FieldTest):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example"]
    expected_out = [(Token("Sec-CH-Example"), {})]
    expected_notes = [ACCEPT_CH_MISSING_VARY]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message = cast(FakeResponseLinter, message)
        message.caching = cast(
            Any, SimpleNamespace(store_shared=True, store_private=True)
        )
