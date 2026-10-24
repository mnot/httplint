from types import SimpleNamespace
from typing import List, cast

from http_sf import Token

from httplint.field.conneg import vary_covers
from httplint.field.structured_field import StructuredField
from httplint.field.tests import FakeRequestLinter, FieldTest
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    CachingProtocol,
    NoteClassListType,
    ResponseLinterProtocol,
    SFListType,
)


class accept_ch(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Accept-CH"
    description = """\
The `Accept-CH` response header field allows servers to indicate the Client Hints that they are
willing to process."""
    reference = "https://www.rfc-editor.org/rfc/rfc8942.html#section-3.1"
    syntax = False  # SF
    category = categories.CONNEG
    deprecated = False
    sf_type = "list"
    value: SFListType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        # Check for valid syntax (must be Tokens)
        for item in self.value:
            if not isinstance(item[0], Token):
                add_note(
                    ACCEPT_CH_BAD_TYPE,
                    ref_uri=self.reference,
                )
                return

    def post_check(self, add_note: AddNoteMethodType) -> None:
        # Warn if the request URI scheme is http
        request = self.message.request
        if request:
            if request.uri and request.uri.lower().startswith("http:"):
                add_note(ACCEPT_CH_IN_PLAIN_HTTP)

        # Check if every field name in Accept-CH is also present in the Vary header
        # if the response is cacheable.
        if hasattr(self.message, "caching") and (
            self.message.caching.store_shared or self.message.caching.store_private
        ):
            # Only Tokens are field names; anything else already got ACCEPT_CH_BAD_TYPE.
            missing_vary = [
                str(item[0])
                for item in self.value
                if isinstance(item[0], Token) and not vary_covers(self.message, str(item[0]))
            ]

            if missing_vary:
                add_note(
                    ACCEPT_CH_MISSING_VARY,
                    missing_fields=", ".join(missing_vary),
                )


class ACCEPT_CH_IN_PLAIN_HTTP(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "Accept-CH is ignored over plain HTTP."
    _text = """\
The `Accept-CH` header field should only be used on secure (HTTPS) responses. Using it over plain
HTTP exposes the user's information to network observers. Because of this, browsers will ignore the
header."""


class ACCEPT_CH_MISSING_VARY(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "Accept-CH lists fields that are missing from Vary."
    _text = """\
The following fields appear in `Accept-CH` but are not listed in the `Vary` header:
`%(missing_fields)s`, even though the response is cacheable.

Because these fields can affect the response content, they should be included in `Vary` to ensure
that caches store separate responses for different client hints."""


class ACCEPT_CH_BAD_TYPE(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The Accept-CH header isn't a List of Tokens."
    _text = """\
The value for this field is legally formatted as a
[Structured Field](https://www.rfc-editor.org/rfc/rfc8941.html), but it isn't a list of Tokens.
As a result, it will likely be ignored by browsers.

See [its definition](%(ref_uri)s) for more information."""


class AcceptCHTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example, Sec-CH-Example-2"]
    expected_out = [(Token("Sec-CH-Example"), {}), (Token("Sec-CH-Example-2"), {})]
    expected_notes: NoteClassListType = []


class AcceptCHBadSyntaxTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b'"foo"']
    expected_out = [("foo", {})]
    expected_notes: NoteClassListType = [
        ACCEPT_CH_BAD_TYPE,
    ]


class AcceptCHHTTPTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example"]
    expected_out = [(Token("Sec-CH-Example"), {})]
    expected_notes = [ACCEPT_CH_IN_PLAIN_HTTP]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        request = FakeRequestLinter()
        request.uri = "http://example.com/"
        message.request = request


class AcceptCHMissingVaryTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b"Sec-CH-Example"]
    expected_out = [(Token("Sec-CH-Example"), {})]
    expected_notes = [ACCEPT_CH_MISSING_VARY]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.caching = cast(
            CachingProtocol, SimpleNamespace(store_shared=True, store_private=True)
        )


def _cacheable_context(message: ResponseLinterProtocol, vary: List[str]) -> None:
    message.caching = cast(CachingProtocol, SimpleNamespace(store_shared=True, store_private=True))
    message.headers.parsed["vary"] = vary


class AcceptCHVaryMixedCaseTest(FieldTest[ResponseLinterProtocol]):
    "Vary values are lowercased; Accept-CH tokens aren't."

    name = "Accept-CH"
    inputs = [b"Sec-CH-UA, Sec-CH-UA-Mobile"]
    expected_out = [(Token("Sec-CH-UA"), {}), (Token("Sec-CH-UA-Mobile"), {})]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, ["sec-ch-ua", "sec-ch-ua-mobile"])


class AcceptCHVaryStarTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b"Sec-CH-UA"]
    expected_out = [(Token("Sec-CH-UA"), {})]
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, ["*"])


class AcceptCHVaryPartialTest(FieldTest[ResponseLinterProtocol]):
    "Guard: main also reports this."

    name = "Accept-CH"
    inputs = [b"Sec-CH-UA, Sec-CH-UA-Mobile"]
    expected_out = [(Token("Sec-CH-UA"), {}), (Token("Sec-CH-UA-Mobile"), {})]
    expected_notes: NoteClassListType = [ACCEPT_CH_MISSING_VARY]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, ["sec-ch-ua"])


class AcceptCHNonTokenVaryIntegerTest(FieldTest[ResponseLinterProtocol]):
    "A non-Token item gets ACCEPT_CH_BAD_TYPE only, not ACCEPT_CH_MISSING_VARY as well."

    name = "Accept-CH"
    inputs = [b"1"]
    expected_out = [(1, {})]
    expected_notes: NoteClassListType = [ACCEPT_CH_BAD_TYPE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, [])


class AcceptCHNonTokenVaryBinaryTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b":YWJj:"]
    expected_out = [(b"abc", {})]
    expected_notes: NoteClassListType = [ACCEPT_CH_BAD_TYPE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, [])


class AcceptCHNonTokenVaryEmptyStringTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-CH"
    inputs = [b'""']
    expected_out = [("", {})]
    expected_notes: NoteClassListType = [ACCEPT_CH_BAD_TYPE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        _cacheable_context(message, [])
