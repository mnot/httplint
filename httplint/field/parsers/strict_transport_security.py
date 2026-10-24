from typing import Any, Optional

from httplint.field.deferred_notes import DeferredNotes
from httplint.field.singleton_field import SINGLE_HEADER_REPEAT, SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_delta_seconds, unquote_string
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)
from httplint.util import inline_safe

sts_dir = rf"(?: {rfc9110.token} (?: {rfc9110.BWS} = {rfc9110.BWS} {rfc9110.parameter_value} )? )"  # pylint: disable=invalid-name
# RFC 6797 Section 6.1: [ directive ] *( ";" [ directive ] ). Whitespace is matched before a ";"
# and before a directive, never twice by neighbouring terms, and the match starts with a
# directive or ";" (the caller strips leading whitespace), so a failed match stays linear. A blank
# value (nothing left once the caller has stripped whitespace) is grammatical too, but is matched
# by its own alternative, so that no term of the pattern can match nothing before whitespace.
sts_directives = (  # pylint: disable=invalid-name
    rf"(?: (?: {sts_dir} | (?= ;) ) (?: {rfc9110.OWS} ; (?: {rfc9110.OWS} {sts_dir} )? )*"
    r" | (?= \Z) )"
)


def _code_span(value: Optional[str]) -> MarkdownSafe:
    "A wire-supplied value as a code span, or '(empty)' if there's nothing to show."
    safe = inline_safe(value or "")
    return MarkdownSafe(f"`{safe}`" if safe.strip() else "(empty)")


def _split_directives(field_value: str) -> list[str]:
    "Split on the ';' separators, ignoring any inside a quoted-string."
    parts: list[str] = []
    start = 0
    quoted = False
    escaped = False
    for pos, char in enumerate(field_value):
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == ";" and not quoted:
            parts.append(field_value[start:pos])
            start = pos + 1
    parts.append(field_value[start:])
    return parts


class strict_transport_security(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Strict-Transport-Security"
    description = """\
The `Strict-Transport-Security` response header (often abbreviated as HSTS) lets a web site tell
browsers that it should only be communicated with using HTTPS, instead of using HTTP."""
    reference = "https://www.rfc-editor.org/rfc/rfc6797"
    syntax = sts_directives
    category = categories.SECURITY
    deprecated = False

    def __init__(self, wire_name: str, message: ResponseLinterProtocol) -> None:
        super().__init__(wire_name, message)
        self._deferred = DeferredNotes()

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> dict[str, Any]:
        parsed: dict[str, Any] = {
            "max-age": None,
            "includesubdomains": False,
            "preload": False,
        }
        # The syntax check sees the unstripped line, so look for other defects in that.
        raw = self.raw_values[0] if self.raw_values else field_value
        raw_directives = _split_directives(raw if raw.strip() == field_value else field_value)
        directives = [d.strip() for d in raw_directives]
        if len(directives) > 1 and directives[-1] == "":
            directives.pop()
            self._deferred.defer(HSTS_TRAILING_SEMICOLON)

        seen_directives = set()
        for index, directive in enumerate(directives):
            parts = directive.split("=", 1)
            name = parts[0].strip().lower()
            value = parts[1].strip() if len(parts) > 1 else None

            if name == "":
                continue  # empty directives are allowed by the grammar

            if name in seen_directives:
                self._deferred.defer(HSTS_DUPLICATE_DIRECTIVE, directive=name)
                continue
            seen_directives.add(name)

            if name == "max-age":
                # directive-value = token / quoted-string; both mean the same (Section 6.2)
                max_age = _code_span(value)
                if value is None:
                    self._deferred.defer(HSTS_BAD_MAX_AGE, max_age=max_age)
                else:
                    if value == "":
                        self._empty_max_age(raw_directives, index)
                    parsed["max-age"] = parse_delta_seconds(
                        unquote_string(value),
                        self._deferred.defer,
                        HSTS_BAD_MAX_AGE,
                        max_digits=4000,  # as for Age: RFC 6797 has no upper bound
                        max_age=max_age,
                    )
            elif name == "includesubdomains":
                parsed["includesubdomains"] = True
                if value is not None:
                    self._deferred.defer(HSTS_VALUE_NOT_ALLOWED, directive="includeSubDomains")
            elif name == "preload":
                parsed["preload"] = True
                if value is not None:
                    self._deferred.defer(HSTS_VALUE_NOT_ALLOWED, directive="preload")
            else:
                # Unknown directive, ignore
                pass

        return parsed

    def _empty_max_age(self, raw_directives: list[str], index: int) -> None:
        """
        An empty `max-age=` is a syntax error that HSTS_BAD_MAX_AGE reports. If it is the value's
        only one (the value would match the syntax with a max-age filled in), drop the generic
        syntax note, so that the defect gets one note.
        """
        name, equals, after = raw_directives[index].partition("=")
        fixed = list(raw_directives)
        fixed[index] = f"{name}{equals}1{after}"
        if self.matches_syntax(";".join(fixed)):
            self.suppress_syntax_note()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        notes_to_add: list[type[Note]] = []
        is_valid = True

        # RFC 6797 Section 8.1:
        # If a UA receives more than one STS header field in an HTTP
        # response message over secure transport, then the UA MUST process
        # only the first such header field.
        parsed = self.value  # already done by SingletonField

        if parsed["preload"]:
            if (
                parsed["includesubdomains"]
                and parsed["max-age"] is not None
                and parsed["max-age"] >= 1536000
            ):
                notes_to_add.append(HSTS_PRELOAD)
            else:
                notes_to_add.append(HSTS_PRELOAD_NOT_SUITABLE)
        else:
            notes_to_add.append(HSTS_NO_PRELOAD)

        if parsed["max-age"] is None:
            if not self._deferred.has(HSTS_BAD_MAX_AGE):
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

        # RFC 6797 Section 8.1: over insecure transport the header is ignored, whatever the
        # status code (a redirect to HTTPS carries no policy).
        if self.message.base_uri and self.message.base_uri.startswith("http:"):
            notes_to_add.append(HSTS_OVER_HTTP)
            is_valid = False

        invalidating_notes = (
            HSTS_DUPLICATE_DIRECTIVE,
            HSTS_BAD_MAX_AGE,
            HSTS_VALUE_NOT_ALLOWED,
        )

        if self._deferred.has(*invalidating_notes):
            is_valid = False

        if is_valid:
            parent = add_note(HSTS_VALID)
        else:
            parent = add_note(HSTS_INVALID)

        self._deferred.emit(parent.add_child)

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
    _summary = "This response's Strict Transport Security (HSTS) header is invalid."
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
    _summary = "The HSTS header contains a duplicate directive."
    _text = """\
The `%(directive)s` directive appears more than once in the `Strict-Transport-Security` header.
Directives must only appear once."""


class HSTS_TRAILING_SEMICOLON(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "The Strict-Transport-Security header has a trailing semicolon."
    _text = """\
The `Strict-Transport-Security` header ends with a semicolon. The grammar allows this, but some
implementations may be confused by it."""


class HSTS_OVER_HTTP(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The HSTS header is sent over HTTP."
    _text = """\
The `Strict-Transport-Security` header is ignored when sent over HTTP, regardless of the status
code (including a redirect to HTTPS). It should only be sent over HTTPS."""


class HSTS_BAD_MAX_AGE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The max-age directive in the HSTS header is invalid."
    _text = """\
The `max-age` directive in the `Strict-Transport-Security` header must be a non-negative
integer. Its value is not valid:

%(max_age)s"""


class HSTS_VALUE_NOT_ALLOWED(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The %(directive)s directive in the HSTS header must not have a value."
    _text = """\
The `%(directive)s` directive in the `Strict-Transport-Security` header is a valueless
directive. It should not have an associated value."""


class HSTSTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains"]
    expected_out = {"max-age": 31536000, "includesubdomains": True, "preload": False}
    expected_notes: NoteClassListType = [HSTS_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_VALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSValidTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; includeSubDomains; preload"]
    expected_out = {"max-age": 31536000, "includesubdomains": True, "preload": True}
    expected_notes: NoteClassListType = [HSTS_SUBDOMAINS, HSTS_PRELOAD, HSTS_VALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSHttpTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_OVER_HTTP,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "http://www.example.com/"


class HSTSDuplicateTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_DUPLICATE_DIRECTIVE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSTripleDuplicateTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000; max-age=100; max-age=200"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_DUPLICATE_DIRECTIVE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSMultipleHeadersTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000", b"max-age=0"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        SINGLE_HEADER_REPEAT,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_VALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSPreloadNotSuitableTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=100; includeSubDomains; preload"]
    expected_out = {"max-age": 100, "includesubdomains": True, "preload": True}
    expected_notes: NoteClassListType = [
        HSTS_SUBDOMAINS,
        HSTS_PRELOAD_NOT_SUITABLE,
        HSTS_SHORT_MAX_AGE,
        HSTS_VALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSShortMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=100"]
    expected_out = {"max-age": 100, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_SHORT_MAX_AGE,
        HSTS_VALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSMaxAgeZeroTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=0"]
    expected_out = {"max-age": 0, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_MAX_AGE_ZERO,
        HSTS_VALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSNoSubdomainsTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [HSTS_NO_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_VALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSPreloadMissingMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"includeSubDomains; preload"]
    expected_out = {"max-age": None, "includesubdomains": True, "preload": True}
    expected_notes: NoteClassListType = [
        HSTS_PRELOAD_NOT_SUITABLE,
        HSTS_NO_MAX_AGE,
        HSTS_SUBDOMAINS,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSBadMaxAgeValueTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=foo"]
    expected_out = {"max-age": None, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_BAD_MAX_AGE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSTrailingSemicolonTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000;includeSubdomains;"]
    expected_out = {"max-age": 31536000, "includesubdomains": True, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_VALID,
        HSTS_TRAILING_SEMICOLON,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSQuotedMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b'max-age="31536000"; includeSubDomains']
    expected_out = {"max-age": 31536000, "includesubdomains": True, "preload": False}
    expected_notes: NoteClassListType = [HSTS_SUBDOMAINS, HSTS_NO_PRELOAD, HSTS_VALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSSignedMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=-5"]
    expected_out = {"max-age": None, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_BAD_MAX_AGE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSPlusMaxAgeTest(HSTSSignedMaxAgeTest):
    inputs = [b"max-age=+5"]


class HSTSUnderscoreMaxAgeTest(HSTSSignedMaxAgeTest):
    inputs = [b"max-age=1_000"]


class HSTSEmptyMaxAgeTest(HSTSSignedMaxAgeTest):
    "The empty value is also a syntax error, which HSTS_BAD_MAX_AGE reports on its own."

    inputs = [b"max-age="]
    expected_notes: NoteClassListType = [
        HSTS_BAD_MAX_AGE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]


class HSTSBareMaxAgeTest(HSTSSignedMaxAgeTest):
    inputs = [b"max-age"]


class HSTSEmptyQuotedMaxAgeTest(HSTSSignedMaxAgeTest):
    inputs = [b'max-age=""']


class HSTSHugeMaxAgeTest(HSTSSignedMaxAgeTest):
    inputs = [b"max-age=" + b"9" * 5000]


class HSTSEmptyDirectivesTest(FieldTest[ResponseLinterProtocol]):
    name = "Strict-Transport-Security"
    inputs = [b"max-age=100;;; includeSubDomains"]
    expected_out = {"max-age": 100, "includesubdomains": True, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_SHORT_MAX_AGE,
        HSTS_VALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSBlankTest(FieldTest[ResponseLinterProtocol]):
    "RFC 6797 Section 6.1 allows no directives at all; HSTS_NO_MAX_AGE is what's wrong with it."

    name = "Strict-Transport-Security"
    inputs = [b""]
    expected_out = {"max-age": None, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_NO_MAX_AGE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://www.example.com/"


class HSTSWhitespaceOnlyTest(HSTSBlankTest):
    inputs = [b"   "]


class HSTSLoneSemicolonTest(HSTSBlankTest):
    inputs = [b";"]
    expected_notes: NoteClassListType = [
        HSTS_NO_MAX_AGE,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
        HSTS_TRAILING_SEMICOLON,
    ]


class HSTSSemicolonsOnlyTest(HSTSLoneSemicolonTest):
    inputs = [b"; ;"]


class HSTSLeadingEmptyDirectiveTest(HSTSEmptyDirectivesTest):
    inputs = [b"; max-age=100; ; includeSubDomains"]


class HSTSRedirectOverHttpTest(FieldTest[ResponseLinterProtocol]):
    "RFC 6797 Section 8.1 has no exception for redirects."

    name = "Strict-Transport-Security"
    inputs = [b"max-age=31536000"]
    expected_out = {"max-age": 31536000, "includesubdomains": False, "preload": False}
    expected_notes: NoteClassListType = [
        HSTS_OVER_HTTP,
        HSTS_NO_SUBDOMAINS,
        HSTS_NO_PRELOAD,
        HSTS_INVALID,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "http://www.example.com/"
        message.status_code = 301
