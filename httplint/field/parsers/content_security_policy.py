from typing import Any, Dict, List, Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


# directive-name = 1*( ALPHA / DIGIT / "-" )
DIRECTIVE_NAME = r"[a-zA-Z0-9-]+"
# directive-value = *( WSP / <VCHAR except ";" and ","> )
DIRECTIVE_VALUE = r"[ \t\x21-\x2B\x2D-\x3A\x3C-\x7E]*"


csp_directive = rf"(?: {DIRECTIVE_NAME} (?: {rfc9110.RWS} {DIRECTIVE_VALUE} )? )"


class content_security_policy(HttpField):
    canonical_name = "Content-Security-Policy"
    description = """\
The `Content-Security-Policy` response header allows web site administrators to declare approved
sources of content that browsers are allowed to load on a page."""
    reference = "https://www.w3.org/TR/CSP3/"

    syntax = rf"(?: {csp_directive} (?: {rfc9110.OWS} ; (?: {rfc9110.OWS} {csp_directive} )? )* )"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    report_only_string = ""
    report_only_text = ""

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        super().__init__(wire_name, message)
        self._deferred_notes: List[Tuple[Any, Dict[str, Any]]] = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Dict[str, str]:
        parsed_directives: Dict[str, str] = {}
        directives = [d.strip() for d in field_value.split(";")]
        duplicate_directives: List[str] = []

        for directive in directives:
            if not directive:
                continue
            parts = directive.split(None, 1)
            name = parts[0].lower()
            value = parts[1] if len(parts) > 1 else ""

            if name in parsed_directives:
                duplicate_directives.append(name)
                continue
            parsed_directives[name] = value

        if duplicate_directives:
            self._deferred_notes.append(
                (
                    CSP_DUPLICATE_DIRECTIVE,
                    {
                        "directives_list": self._make_list(duplicate_directives),
                        "report_only_text": self.report_only_text,
                    },
                )
            )

        return parsed_directives

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value:
            parent = add_note(
                CONTENT_SECURITY_POLICY,
                report_only=self.report_only_string,
                report_only_text=self.report_only_text,
            )
        else:
            return

        for note_cls, note_params in self._deferred_notes:
            parent.add_child(note_cls, **note_params)

        unsafe_inline_directives = []
        unsafe_eval_directives = []
        http_uri_directives = []
        wide_open_directives = []
        deprecated_report_uri = False

        for parsed_directives in self.value:
            for name, value in parsed_directives.items():
                if name == "report-uri":
                    deprecated_report_uri = True

                if name in ["script-src", "style-src", "object-src"]:
                    if "*" in value.split():
                        wide_open_directives.append(name)

                if "'unsafe-inline'" in value:
                    unsafe_inline_directives.append(name)
                if "'unsafe-eval'" in value:
                    unsafe_eval_directives.append(name)
                # Check for http: scheme or literal http://
                if "http:" in value or "http://" in value:
                    # Simple check, could be improved to parse source lists
                    if "http:" in value.split():
                        http_uri_directives.append(name)

        if deprecated_report_uri:
            parent.add_child(
                CSP_DEPRECATED_REPORT_URI,
                report_only_text=self.report_only_text,
            )
        if wide_open_directives:
            parent.add_child(
                CSP_WIDE_OPEN,
                directives_list=self._make_list(wide_open_directives),
                report_only_text=self.report_only_text,
            )
        if unsafe_inline_directives:
            parent.add_child(
                CSP_UNSAFE_INLINE,
                directives_list=self._make_list(unsafe_inline_directives),
                report_only_text=self.report_only_text,
            )
        if unsafe_eval_directives:
            parent.add_child(
                CSP_UNSAFE_EVAL,
                directives_list=self._make_list(unsafe_eval_directives),
                report_only_text=self.report_only_text,
            )
        if http_uri_directives:
            parent.add_child(
                CSP_HTTP_URI,
                directives_list=self._make_list(http_uri_directives),
                report_only_text=self.report_only_text,
            )

    def post_check(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        reporting_endpoints_field = message.headers.parsed.get("reporting-endpoints")
        reporting_endpoints = (
            list(reporting_endpoints_field.keys()) if reporting_endpoints_field else []
        )

        known_endpoints = set(reporting_endpoints)

        for parsed_directives in self.value:
            for name, value in parsed_directives.items():
                if name != "report-to":
                    continue
                if value in known_endpoints:
                    continue

                # Find the parent note
                parent_note = None
                for note in message.notes:
                    if isinstance(note, CONTENT_SECURITY_POLICY):
                        parent_note = note
                        break

                if parent_note:
                    parent_note.add_child(
                        CSP_REPORT_TO_MISSING,
                        endpoint=value,
                        report_only_text=self.report_only_text,
                    )
                else:
                    # Fallback if parent not found (should be rare)
                    add_note(
                        CSP_REPORT_TO_MISSING,
                        endpoint=value,
                        report_only_text=self.report_only_text,
                    )

    def _make_list(self, items: list[str]) -> str:
        return "\n".join([f"* `{item}`" for item in items])


class CONTENT_SECURITY_POLICY(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response sets a Content Security Policy%(report_only)s."
    _text = """\
[Content Security Policy](https://www.w3.org/TR/CSP3/) allows the server to declare
the sources of content that browsers are allowed to use on a page.%(report_only_text)s"""


class CSP_UNSAFE_INLINE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Inline scripts are allowed."
    _text = """\
The `'unsafe-inline'` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive allows the execution of inline scripts and event handlers, which
significantly reduces the protection provided by CSP against Cross-Site
Scripting (XSS) attacks.

It was found in the following directives:

%(directives_list)s"""


class CSP_UNSAFE_EVAL(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Unsafe script evaluation is allowed."
    _text = """\
The `'unsafe-eval'` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive allows the use of string-to-code mechanisms like `eval()`, which can make it easier for
attackers to execute malicious code.

It was found in the following directives:

%(directives_list)s"""


class CSP_HTTP_URI(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Loading from insecure HTTP sources is allowed."
    _text = """\
Allowing `http:` sources in `%(field_name)s` can allow attackers to intercept and modify
content loaded by the page, potentially bypassing security controls.

It was found in the following directives:

%(directives_list)s"""


class CSP_DUPLICATE_DIRECTIVE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Duplicate directives are present."
    _text = """\
Directives must only appear once in the `%(field_name)s` header; subsequent occurrences are ignored.

The following directives were duplicated:

%(directives_list)s"""


class CSP_DEPRECATED_REPORT_URI(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The deprecated report-uri directive is used."
    _text = """\
The `report-uri` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive is deprecated in favor of `report-to`. It is recommended to use `report-to`
for reporting violations, although `report-uri` may still be supported for backward
compatibility."""


class CSP_WIDE_OPEN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "All sources are allowed in one or more directives."
    _text = """\
The `*` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive allows resources to be loaded from any origin, which significantly reduces the protection
provided by CSP.%(report_only_text)s

It was found in the following directives:

%(directives_list)s"""


class CSP_REPORT_TO_MISSING(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The report-to endpoint '%(endpoint)s' is not defined."
    _text = """\
The `report-to` directive [Content Security Policy](https://www.w3.org/TR/CSP3/)
specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header.%(report_only_text)s"""


class CSPTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = [{"default-src": "'self'", "script-src": "'unsafe-inline'"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]


class CSPMultipleTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'", b"script-src 'unsafe-eval'"]
    expected_out = [{"default-src": "'self'"}, {"script-src": "'unsafe-eval'"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_EVAL]


class CSPDuplicateTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; default-src 'none'"]
    expected_out = [{"default-src": "'self'"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_DUPLICATE_DIRECTIVE]


class CSPReportUriTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"report-uri /csp-report"]
    expected_out = [{"report-uri": "/csp-report"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_DEPRECATED_REPORT_URI]


class CSPWideOpenTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"script-src *"]
    expected_out = [{"script-src": "*"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_WIDE_OPEN]


class CSPTrailingSemiTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; script-src 'self';"]
    expected_out = [{"default-src": "'self'", "script-src": "'self'"}]
    expected_notes = [CONTENT_SECURITY_POLICY]


class CSPReportToTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"sort-src 'self'; report-to endpoint"]
    expected_out = [{"sort-src": "'self'", "report-to": "endpoint"}]
    expected_notes = [CONTENT_SECURITY_POLICY]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CSPReportToMissingTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'self'; report-to endpoint"]
    expected_out = [{"script-src": "'self'", "report-to": "endpoint"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_REPORT_TO_MISSING]


class CSPReportToMismatchTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'self'; report-to endpoint"]
    expected_out = [{"script-src": "'self'", "report-to": "endpoint"}]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_REPORT_TO_MISSING]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process([(b"Reporting-Endpoints", b'endpoint-2="https://example.com"')])
