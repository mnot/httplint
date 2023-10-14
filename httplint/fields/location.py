import re
from urllib.parse import urljoin

from httplint.fields import HttpField
from httplint.fields._test import FieldTest
from httplint.message import HttpMessageLinter, HttpResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7231, rfc3986
from httplint.types import AddNoteMethodType


class location(HttpField):
    canonical_name = "Location"
    description = """\
The `Location` header is used in `3xx` responses to redirect the recipient to a different location
to complete the request.

In `201 Created` responses, it identifies a newly created resource."""
    reference = f"{rfc7231.SPEC_URL}#header.location"
    syntax = rfc7231.Location
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if isinstance(
            self.message, HttpResponseLinter
        ) and self.message.status_code not in [
            201,
            300,
            301,
            302,
            303,
            305,
            307,
            308,
        ]:
            add_note(LOCATION_UNDEFINED)
        if not re.match(rf"^\s*{rfc3986.URI}\s*$", field_value, re.VERBOSE):
            add_note(
                LOCATION_NOT_ABSOLUTE,
                full_uri=urljoin(self.message.base_uri, field_value),
            )
        return field_value


class LOCATION_UNDEFINED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "%(response)s doesn't define any meaning for the Location header."
    _text = """\
The `Location` header is used for specific purposes in HTTP; mostly to indicate the URI of another
resource (e.g., in redirection, or when a new resource is created).

In other status codes (such as this one) it doesn't have a defined meaning, so any use of it won't
be interoperable.

Sometimes `Location` is confused with `Content-Location`, which indicates a URI for the payload of
the message that it appears in."""


class LOCATION_NOT_ABSOLUTE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The Location header contains a relative URI."
    _text = """\
`Location` was originally specified to contain an absolute, not relative, URI.

It is in the process of being updated, and most clients will work around this.

The correct absolute URI is (probably): `%(full_uri)s`"""


class LocationTest(FieldTest):
    name = "Location"
    inputs = [b"http://other.example.com/foo"]
    expected_out = "http://other.example.com/foo"

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 300  # type: ignore
