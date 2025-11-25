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

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value:
            add_note(CONTENT_SECURITY_POLICY, report_only=self.report_only_string)
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
                    add_note(CSP_DUPLICATE_DIRECTIVE, directive=name)
                    continue
                parsed_directives[name] = value

            for name, value in parsed_directives.items():
                if name == "report-uri":
                    add_note(CSP_DEPRECATED_REPORT_URI)

                if name in ["script-src", "style-src", "object-src"]:
                    if "*" in value.split():
                        add_note(CSP_WIDE_OPEN, directive=name)

                if "'unsafe-inline'" in value:
                    add_note(CSP_UNSAFE_INLINE)
                if "'unsafe-eval'" in value:
                    add_note(CSP_UNSAFE_EVAL)
                # Check for http: scheme or literal http://
                if "http:" in value or "http://" in value:
                    # Simple check, could be improved to parse source lists
                    if "http:" in value.split():
                        add_note(CSP_HTTP_URI)


class CONTENT_SECURITY_POLICY(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "%(message)s sets a content security policy%(report_only)s."
    _text = """\
The `%(field_name)s` header allows web site administrators to declare approved
sources of content that browsers are allowed to load on a page."""


class CSP_UNSAFE_INLINE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows inline scripts."
    _text = """\
Using `'unsafe-inline'` in `%(field_name)s` allows the execution of inline scripts and
event handlers, which significantly reduces the protection provided by CSP against Cross-Site
Scripting (XSS) attacks."""


class CSP_UNSAFE_EVAL(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows unsafe evaluation."
    _text = """\
Using `'unsafe-eval'` in `%(field_name)s` allows the use of string-to-code mechanisms like
`eval()`, which can make it easier for attackers to execute malicious code."""


class CSP_HTTP_URI(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows insecure HTTP sources."
    _text = """\
Allowing `http:` sources in `%(field_name)s` can allow attackers to intercept and modify
content loaded by the page, potentially bypassing security controls."""


class CSP_DUPLICATE_DIRECTIVE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s contains a duplicate directive."
    _text = """\
The `%(directive)s` directive appears more than once in the `%(field_name)s` header.
Directives must only appear once; subsequent occurrences are ignored."""


class CSP_DEPRECATED_REPORT_URI(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s's %(field_name)s uses the deprecated report-uri directive."
    _text = """\
The `report-uri` directive is deprecated in favor of `report-to`. It is recommended to use `report-to`
for reporting violations, although `report-uri` may still be supported for backward
compatibility."""


class CSP_WIDE_OPEN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s's %(field_name)s allows all sources one or more directives."
    _text = """\
Using `*` in `%(directive)s` allows resources to be loaded from any origin, which significantly
reduces the protection provided by CSP."""


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
