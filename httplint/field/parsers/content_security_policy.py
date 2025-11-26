from httplint.field import HttpField
from httplint.field.tests import FieldTest
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

    syntax = (
        rf"(?: {csp_directive} (?: {rfc9110.OWS} ; {rfc9110.OWS} {csp_directive} )* )"
    )
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    report_only_string = ""
    report_only_text = ""

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value:
            add_note(
                CONTENT_SECURITY_POLICY,
                report_only=self.report_only_string,
                report_only_text=self.report_only_text,
            )

        unsafe_inline_directives = []
        unsafe_eval_directives = []
        http_uri_directives = []
        wide_open_directives = []
        duplicate_directives = []
        deprecated_report_uri = False

        for policy in self.value:
            parsed_directives = {}
            directives = [d.strip() for d in policy.split(";")]
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

        if duplicate_directives:
            add_note(
                CSP_DUPLICATE_DIRECTIVE,
                directives_list=self._make_list(duplicate_directives),
                report_only_text=self.report_only_text,
            )
        if deprecated_report_uri:
            add_note(
                CSP_DEPRECATED_REPORT_URI,
                report_only_text=self.report_only_text,
            )
        if wide_open_directives:
            add_note(
                CSP_WIDE_OPEN,
                directives_list=self._make_list(wide_open_directives),
                report_only_text=self.report_only_text,
            )
        if unsafe_inline_directives:
            add_note(
                CSP_UNSAFE_INLINE,
                directives_list=self._make_list(unsafe_inline_directives),
                report_only_text=self.report_only_text,
            )
        if unsafe_eval_directives:
            add_note(
                CSP_UNSAFE_EVAL,
                directives_list=self._make_list(unsafe_eval_directives),
                report_only_text=self.report_only_text,
            )
        if http_uri_directives:
            add_note(
                CSP_HTTP_URI,
                directives_list=self._make_list(http_uri_directives),
                report_only_text=self.report_only_text,
            )

    def _make_list(self, items: list[str]) -> str:
        return "\n".join([f"* `{item}`" for item in items])


class CONTENT_SECURITY_POLICY(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "%(message)s sets a content security policy%(report_only)s."
    _text = """\
[Content Security Policy](https://www.w3.org/TR/CSP3/) allows the server to declare
the sources of content that browsers are allowed to use on a page.%(report_only_text)s"""


class CSP_UNSAFE_INLINE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows inline scripts."
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
    _summary = "%(message)s's %(field_name)s allows unsafe evaluation."
    _text = """\
The `'unsafe-eval'` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive allows the use of string-to-code mechanisms like `eval()`, which can make it easier for
attackers to execute malicious code.

It was found in the following directives:

%(directives_list)s"""


class CSP_HTTP_URI(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows insecure HTTP sources."
    _text = """\
Allowing `http:` sources in `%(field_name)s` can allow attackers to intercept and modify
content loaded by the page, potentially bypassing security controls.

It was found in the following directives:

%(directives_list)s"""


class CSP_DUPLICATE_DIRECTIVE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s contains duplicate directives."
    _text = """\
Directives must only appear once in the `%(field_name)s` header; subsequent occurrences are ignored.

The following directives were duplicated:

%(directives_list)s"""


class CSP_DEPRECATED_REPORT_URI(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s's %(field_name)s uses the deprecated report-uri directive."
    _text = """\
The `report-uri` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive is deprecated in favor of `report-to`. It is recommended to use `report-to`
for reporting violations, although `report-uri` may still be supported for backward
compatibility."""


class CSP_WIDE_OPEN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "%(message)s's %(field_name)s allows all sources in one or more directives."
    )
    _text = """\
The `*` [Content Security Policy](https://www.w3.org/TR/CSP3/)
directive allows resources to be loaded from any origin, which significantly reduces the protection
provided by CSP.%(report_only_text)s

It was found in the following directives:

%(directives_list)s"""


class CSPTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = ["default-src 'self'; script-src 'unsafe-inline'"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]


class CSPMultipleTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'", b"script-src 'unsafe-eval'"]
    expected_out = ["default-src 'self'", "script-src 'unsafe-eval'"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_EVAL]


class CSPDuplicateTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; default-src 'none'"]
    expected_out = ["default-src 'self'; default-src 'none'"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_DUPLICATE_DIRECTIVE]


class CSPReportUriTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"report-uri /csp-report"]
    expected_out = ["report-uri /csp-report"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_DEPRECATED_REPORT_URI]


class CSPWideOpenTest(FieldTest):
    name = "Content-Security-Policy"
    inputs = [b"script-src *"]
    expected_out = ["script-src *"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_WIDE_OPEN]
