from typing import Any

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.field.notes import BAD_SYNTAX
from httplint.message import HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


sts_directive = (
    rf"(?: {rfc9110.token} (?: {rfc9110.BWS} = {rfc9110.BWS} {rfc9110.parameter_value} )? )"
)


class strict_transport_security(HttpField):
    canonical_name = "Strict-Transport-Security"
    description = """\
The `Strict-Transport-Security` response header (often abbreviated as HSTS) lets a web site tell
browsers that it should only be communicated with using HTTPS, instead of using HTTP."""
    reference = "https://tools.ietf.org/html/rfc6797"
    syntax = rf"(?: {sts_directive} (?: {rfc9110.OWS} ; {rfc9110.OWS} {sts_directive} )* )"
    list_header = False
    nonstandard_syntax = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> dict[str, Any]:
        parsed: dict[str, Any] = {
            "max-age": None,
            "includesubdomains": False,
            "preload": False,
        }
        directives = [d.strip() for d in field_value.split(";")]
        seen_directives = set()
        for directive in directives:
            parts = directive.split("=", 1)
            name = parts[0].strip().lower()
            value = parts[1].strip() if len(parts) > 1 else None

            if name in seen_directives:
                add_note(HSTS_DUPLICATE_DIRECTIVE, directive=name)
                continue
            seen_directives.add(name)

            if name == "max-age":
                try:
                    parsed["max-age"] = int(value)  # type: ignore
                except (ValueError, TypeError):
                    add_note(BAD_SYNTAX, f"Invalid max-age value: {value}")
            elif name == "includesubdomains":
                parsed["includesubdomains"] = True
                if value is not None:
                    add_note(
                        BAD_SYNTAX, "includeSubDomains directive must not have a value"
                    )
            elif name == "preload":
                parsed["preload"] = True
                if value is not None:
                    add_note(BAD_SYNTAX, "preload directive must not have a value")
            else:
                # Unknown directive, ignore
                pass

        return parsed

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        if len(self.value) > 1:
            add_note(HSTS_MULTIPLE_HEADERS)

        # RFC 6797 Section 8.1:
        # If a UA receives more than one STS header field in an HTTP
        # response message over secure transport, then the UA MUST process
        # only the first such header field.
        parsed = self.value[0]

        if parsed["max-age"] is None:
            add_note(HSTS_NO_MAX_AGE)
        elif parsed["max-age"] == 0:
            add_note(HSTS_MAX_AGE_ZERO)

        if parsed["includesubdomains"]:
            add_note(HSTS_SUBDOMAINS)
        if parsed["preload"]:
            add_note(HSTS_PRELOAD)

        if self.message.base_uri and self.message.base_uri.startswith("http:"):
            if hasattr(self.message, "status_code") and self.message.status_code != 301:
                add_note(HSTS_OVER_HTTP)


class HSTS_NO_MAX_AGE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "%(message)s's HSTS header doesn't contain a max-age directive."
    _text = """\
The `Strict-Transport-Security` header requires a `max-age` directive to be valid."""


class HSTS_SUBDOMAINS(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s's HSTS policy applies to subdomains."
    _text = """\
The `includeSubDomains` directive indicates that this HSTS policy applies to this domain as well as
all of its subdomains."""


class HSTS_PRELOAD(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s's HSTS policy allows preloading."
    _text = """\
The `preload` directive indicates that the site owner consents to have their domain preloaded in
browser HSTS lists."""


class HSTS_MAX_AGE_ZERO(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's HSTS policy has a max-age of 0."
    _text = """\
A `max-age` of 0 tells the browser to expire the HSTS policy immediately, effectively disabling
it."""


class HSTS_DUPLICATE_DIRECTIVE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's HSTS header contains a duplicate directive."
    _text = """\
The `%(directive)s` directive appears more than once in the `Strict-Transport-Security` header.
Directives must only appear once."""


class HSTS_OVER_HTTP(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's HSTS header is sent over HTTP."
    _text = """\
The `Strict-Transport-Security` header is ignored when sent over HTTP, unless it's a 301 Redirect.
It should only be sent over HTTPS."""


class HSTS_MULTIPLE_HEADERS(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s has multiple HSTS headers."
    _text = """\
A response should only contain a single `Strict-Transport-Security` header.
User agents are required to process only the first one and ignore the rest."""


class HSTSTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains"]
    expected_out = [{"max-age": 31536000, "includesubdomains": True, "preload": False}]
    expected_notes = [HSTS_SUBDOMAINS]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSHttpTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [HSTS_OVER_HTTP]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "http://www.example.com/"


class HSTSDuplicateTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [HSTS_DUPLICATE_DIRECTIVE]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSTripleDuplicateTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100; max-age=200"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [HSTS_DUPLICATE_DIRECTIVE]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSMultipleHeadersTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000", b"max-age=0"]
    expected_out = [
        {"max-age": 31536000, "includesubdomains": False, "preload": False},
        {"max-age": 0, "includesubdomains": False, "preload": False},
    ]
    expected_notes = [HSTS_MULTIPLE_HEADERS]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"
