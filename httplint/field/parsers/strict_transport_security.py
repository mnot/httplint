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
        is_valid = True

        if len(self.value) > 1:
            notes_to_add.append(HSTS_MULTIPLE_HEADERS)

        # RFC 6797 Section 8.1:
        # If a UA receives more than one STS header field in an HTTP
        # response message over secure transport, then the UA MUST process
        # only the first such header field.
        parsed = self.value[0]

        if parsed["preload"]:
            if parsed["includesubdomains"] and parsed["max-age"] >= 1536000:
                notes_to_add.append(HSTS_PRELOAD)
            else:
                notes_to_add.append(HSTS_PRELOAD_NOT_SUITABLE)
        else:
            notes_to_add.append(HSTS_NO_PRELOAD)

        if parsed["max-age"] is None:
            notes_to_add.append(HSTS_NO_MAX_AGE)
            is_valid = False
        elif parsed["max-age"] == 0:
            notes_to_add.append(HSTS_MAX_AGE_ZERO)
        elif parsed["max-age"] < 1536000:
            notes_to_add.append(HSTS_SHORT_MAX_AGE)

        if parsed["includesubdomains"]:
            notes_to_add.append(HSTS_SUBDOMAINS)
        else:
            notes_to_add.append(HSTS_NO_SUBDOMAINS)

        if self.message.base_uri and self.message.base_uri.startswith("http:"):
            if hasattr(self.message, "status_code") and self.message.status_code != 301:
                notes_to_add.append(HSTS_OVER_HTTP)
                is_valid = False

        invalidating_notes = (
            HSTS_DUPLICATE_DIRECTIVE,
            HSTS_BAD_MAX_AGE,
            HSTS_VALUE_NOT_ALLOWED,
        )

        for note in self.message.notes:
            if isinstance(note, invalidating_notes):
                is_valid = False
                break

        if is_valid:
            parent = add_note(HSTS_VALID)
        else:
            parent = add_note(HSTS_INVALID)

        for note_cls in notes_to_add:
            parent.add_child(note_cls)


class HSTS_VALID(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "Strict Transport Security (HSTS) is enabled."
    _text = """\
This site has enabled HTTP Strict Transport Security (HSTS), which tells the browser to only
communicate with it over a secure connection."""


class HSTS_INVALID(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "%(message)s's Strict Transport Security (HSTS) header is invalid."
    _text = """\
This site has attempted to enable HTTP Strict Transport Security (HSTS), which tells the browser to only
communicate with it over a secure connection.

However, one or more issues prevent it from being valid. See the child notes for details."""


class HSTS_NO_MAX_AGE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "There is no max-age directive."
    _text = """\
The `Strict-Transport-Security` header requires a `max-age` directive to be valid."""


class HSTS_MAX_AGE_ZERO(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The max-age is 0."
    _text = """\
A `max-age` of 0 tells the browser to expire the `Strict-Transport-Security` policy immediately,
effectively disabling it."""


class HSTS_SHORT_MAX_AGE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The max-age is less than one year."
    _text = """\
Most sites should set a `max-age` of at least one year on `Strict-Transport-Security`."""


class HSTS_SUBDOMAINS(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "HSTS applies to subdomains."
    _text = """\
The `includeSubDomains` directive indicates that this HSTS policy applies to this domain as well as
all of its subdomains."""


class HSTS_NO_SUBDOMAINS(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "HSTS doesn't apply to subdomains."
    _text = """\
The `includeSubDomains` directive indicates that this HSTS policy applies to this domain as well as
all of its subdomains.

Because cookies can be set across HTTP and HTTPS sites as well as across subdomains, this means 
that an attacker might be able to take advantage of a subdomain that doesn't have HSTS enabled.
"""


class HSTS_PRELOAD(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "Browser preloading is allowed."
    _text = """\
The `preload` directive on `Strict-Transport-Security` allows browsers to preload the site in
its HSTS lists, avoiding the potential for making unencrypted requests when first accessing the
site.

See the [HSTS Preload List](https://hstspreload.org/) for more information.
"""


class HSTS_PRELOAD_NOT_SUITABLE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "Browser preloading is allowed, but this policy isn't suitable for it."
    _text = """\
Preloading a site in a browser's HSTS list requires a `max-age` of at least one year and the
`includeSubDomains` directive.

See the [HSTS Preload List](https://hstspreload.org/) for more information.
"""


class HSTS_NO_PRELOAD(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "Browser preloading isn't allowed."
    _text = """\
Without a `preload` directive, browsers may make an unencrypted request when first accessing the
site, potentially exposing sensitive information.

See the [HSTS Preload List](https://hstspreload.org/) for more information.
"""


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


class HSTSTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains"]
    expected_out = [{"max-age": 31536000, "includesubdomains": True, "preload": False}]
    expected_notes = [HSTS_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_VALID]

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
    expected_notes = [HSTS_OVER_HTTP, HSTS_NO_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_INVALID]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "http://www.example.com/"


class HSTSDuplicateTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [
        HSTS_DUPLICATE_DIRECTIVE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSTripleDuplicateTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100; max-age=200"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [
        HSTS_DUPLICATE_DIRECTIVE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSMultipleHeadersTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000", b"max-age=0"]
    expected_out = [
        {"max-age": 31536000, "includesubdomains": False, "preload": False},
        {"max-age": 0, "includesubdomains": False, "preload": False},
    ]
    expected_notes = [
        HSTS_MULTIPLE_HEADERS,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_VALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSPreloadNotSuitableTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=100; includeSubDomains; preload"]
    expected_out = [{"max-age": 100, "includesubdomains": True, "preload": True}]
    expected_notes = [
        HSTS_SUBDOMAINS,
        HSTS_PRELOAD_NOT_SUITABLE,
        HSTS_SHORT_MAX_AGE,
        HSTS_VALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSShortMaxAgeTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=100"]
    expected_out = [{"max-age": 100, "includesubdomains": False, "preload": False}]
    expected_notes = [
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_SHORT_MAX_AGE,
        HSTS_VALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSMaxAgeZeroTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=0"]
    expected_out = [{"max-age": 0, "includesubdomains": False, "preload": False}]
    expected_notes = [
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_MAX_AGE_ZERO,
        HSTS_VALID,
    ]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSNoSubdomainsTest(FieldTest):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000"]
    expected_out = [{"max-age": 31536000, "includesubdomains": False, "preload": False}]
    expected_notes = [HSTS_NO_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_VALID]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.base_uri = "https://www.example.com/"
