from dataclasses import dataclass
from typing import List

from httplint.field.broken_field import BrokenField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.types import AddNoteMethodType, RequestLinterProtocol


@dataclass
class CookiePair:
    name: str
    value: str


class cookie(BrokenField[RequestLinterProtocol]):
    canonical_name = "Cookie"
    description = """\
The `Cookie` header field contains stored HTTP cookies previously sent by the server with the
`Set-Cookie` header."""
    reference = "https://www.rfc-editor.org/rfc/rfc6265.html#section-4.2"
    syntax = False
    category = categories.COOKIES
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> List[CookiePair]:
        # RFC 6265 Section 4.1.1
        # cookie-string = cookie-pair *( ";" SP cookie-pair )
        pairs: List[CookiePair] = []

        # Split by ";" to handle semicolon-separated pairs within a single header value.
        items = field_value.split(";")
        for item in items:
            item = item.strip()
            if not item:
                continue

            if "=" in item:
                name, value = item.split("=", 1)
            else:
                name = ""
                value = item

            # Validation for allowed characters in cookie-name and cookie-value not yet handled.
            # cookie-octet = %x21 / %x23-2B / %x2D-3A / %x3C-5B / %x5D-7E
            # Excluding: CTLs, SP, DQUOTE, comma, semicolon, backslash

            # RFC 6265 4.1.1 says:
            # cookie-pair       = cookie-name "=" cookie-value
            # cookie-name       = token
            # cookie-value      = *cookie-octet / ( DQUOTE *cookie-octet DQUOTE )

            pairs.append(CookiePair(name, value))

        return pairs


class CookieTest(FieldTest[RequestLinterProtocol]):
    name = "Cookie"
    inputs = [b"SID=31d4d96e407aad42"]
    expected_out = [[CookiePair("SID", "31d4d96e407aad42")]]

    def test_multiple_pairs(self) -> None:
        self.inputs = [b"SID=31d4d96e407aad42; lang=en-US"]
        self.expected_out = [[CookiePair("SID", "31d4d96e407aad42"), CookiePair("lang", "en-US")]]
        self.setUp()
        self.test_header()

    def test_multiple_headers(self) -> None:
        self.inputs = [b"SID=31d4d96e407aad42", b"lang=en-US"]
        # BrokenField collates all values into a list of parsed results.
        # Each parse returns a list of CookiePairs.
        self.expected_out = [
            [CookiePair("SID", "31d4d96e407aad42")],
            [CookiePair("lang", "en-US")],
        ]
        self.setUp()
        self.test_header()
