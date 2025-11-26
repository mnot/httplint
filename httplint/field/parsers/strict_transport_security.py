from typing import Any

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


sts_dir = rf"(?: {rfc9110.token} (?: {rfc9110.BWS} = {rfc9110.BWS} {rfc9110.parameter_value} )? )"


class strict_transport_security(HttpField):
    canonical_name = "Strict-Transport-Security"
    description = """\
The `Strict-Transport-Security` response header (often abbreviated as HSTS) lets a web site tell
browsers that it should only be communicated with using HTTPS, instead of using HTTP."""
    reference = "https://www.rfc-editor.org/rfc/rfc6797"
    syntax = rf"(?: {sts_dir} (?: {rfc9110.OWS} ; {rfc9110.OWS} {sts_dir} )* )"
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
                    add_note(HSTS_BAD_MAX_AGE, max_age=str(value))
            elif name == "includesubdomains":
                parsed["includesubdomains"] = True
                if value is not None:
                    add_note(HSTS_VALUE_NOT_ALLOWED, directive="includeSubDomains")
            elif name == "preload":
                parsed["preload"] = True
                if value is not None:
                    add_note(HSTS_VALUE_NOT_ALLOWED, directive="preload")
            else:
                # Unknown directive, ignore
                pass

        return parsed

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        notes_to_add: list[type[Note]] = []

        if len(self.value) > 1:
            notes_to_add.append(HSTS_MULTIPLE_HEADERS)

        # RFC 6797 Section 8.1:
        # If a UA receives more than one STS header field in an HTTP
        # response message over secure transport, then the UA MUST process
        # only the first such header field.
        parsed = self.value[0]

        if parsed["max-age"] is None:
            notes_to_add.append(HSTS_NO_MAX_AGE)
        elif parsed["max-age"] == 0:
            notes_to_add.append(HSTS_MAX_AGE_ZERO)

        if parsed["includesubdomains"]:
            notes_to_add.append(HSTS_SUBDOMAINS)
        if parsed["preload"]:
            notes_to_add.append(HSTS_PRELOAD)

        if self.message.base_uri and self.message.base_uri.startswith("http:"):
            if hasattr(self.message, "status_code") and self.message.status_code != 301:
                notes_to_add.append(HSTS_OVER_HTTP)

        invalidating_notes = (
            HSTS_NO_MAX_AGE,
            HSTS_MAX_AGE_ZERO,
            HSTS_DUPLICATE_DIRECTIVE,
            HSTS_OVER_HTTP,
            HSTS_MULTIPLE_HEADERS,
            HSTS_BAD_MAX_AGE,
            HSTS_VALUE_NOT_ALLOWED,
        )

        is_valid = True
        for note in self.message.notes:
            if isinstance(note, invalidating_notes):
                is_valid = False
                break

        if is_valid:
            for note_cls in notes_to_add:
                if issubclass(note_cls, invalidating_notes):
                    is_valid = False
                    break

        if is_valid:
            add_note(HSTS_VALID)

        for note_cls in notes_to_add:
            add_note(note_cls)


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
    _summary = "%(message)s's HSTS policy allows browser preloading."
    _text = """\
The `preload` directive on `Strict-Transport-Security` indicates that the site owner consents
to have their domain preloaded in browser HSTS lists."""


class HSTS_MAX_AGE_ZERO(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's HSTS policy has a max-age of 0."
    _text = """\
A `max-age` of 0 tells the browser to expire the `Strict-Transport-Security` policy immediately,
effectively disabling it."""


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


class HSTS_BAD_MAX_AGE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The max-age directive in the HSTS header is invalid."
    _text = """\
The `max-age` directive in the `Strict-Transport-Security` header must be a non-negative
integer. The value "%(max_age)s" is not valid."""


class HSTS_VALUE_NOT_ALLOWED(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The %(directive)s directive in the HSTS header must not have a value."
    _text = """\
The `%(directive)s` directive in the `Strict-Transport-Security` header is a valueless
directive. It should not have an associated value."""


class HSTS_VALID(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "Strict Transport Security (HSTS) is enabled."
    _text = """\
This site has enabled HTTP Strict Transport Security (HSTS), which tells the browser to only
communicate with it over a secure connection."""


class HSTSTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains"]
    expected_out = [{"max-age": 31536000, "includesubdomains": True, "preload": False}]
    expected_notes = [HSTS_SUBDOMAINS, HSTS_VALID]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSValidTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains; preload"]
    expected_out = [{"max-age": 31536000, "includesubdomains": True, "preload": True}]
    expected_notes = [HSTS_SUBDOMAINS, HSTS_PRELOAD, HSTS_VALID]

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
