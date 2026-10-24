from typing import Dict, List, Optional

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.reporting import known_reporting_endpoints
from httplint.field.tests import FieldTest
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteArgsType,
    NoteClassListType,
    ResponseLinterProtocol,
)
from httplint.util import inline_safe

# directive-name = 1*( ALPHA / DIGIT / "-" )
DIRECTIVE_NAME = r"[a-zA-Z0-9-]+"
# directive-value = *( WSP / <VCHAR except ";" and ","> )
# Expressed as whitespace-separated runs of non-whitespace, so a value can neither start nor end
# in whitespace; otherwise it overlaps the surrounding RWS / OWS and the regex backtracks badly.
DIRECTIVE_VALUE_CHARS = r"[\x21-\x2B\x2D-\x3A\x3C-\x7E]+"
DIRECTIVE_VALUE = rf"(?: {DIRECTIVE_VALUE_CHARS} (?: {rfc9110.RWS} {DIRECTIVE_VALUE_CHARS} )* )"


# Whitespace after a directive is only consumed when a character other than SP, HTAB or ";" follows
# it. That keeps it from overlapping the OWS before ";" and the trailing \s* added by
# HttpListField, while still putting the error position of a bad byte after the whitespace.
TRAILING_WS = r"(?: [ \t]+ (?= [^ \t;] ) )?"

csp_directive = rf"(?: {DIRECTIVE_NAME} (?: {rfc9110.RWS} {DIRECTIVE_VALUE} )? {TRAILING_WS} )"  # pylint: disable=invalid-name

# Fetch directives (CSP3 section 6.1); only these load content, so only they get the http: check.
FETCH_DIRECTIVES = {
    "default-src",
    "script-src",
    "script-src-elem",
    "script-src-attr",
    "style-src",
    "style-src-elem",
    "style-src-attr",
    "img-src",
    "font-src",
    "connect-src",
    "media-src",
    "object-src",
    "frame-src",
    "child-src",
    "worker-src",
    "manifest-src",
    "prefetch-src",
}


class content_security_policy(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Content-Security-Policy"
    description = """\
The `Content-Security-Policy` response header allows web site administrators to declare approved
sources of content that browsers are allowed to load on a page."""
    reference = "https://www.w3.org/TR/CSP3/"

    syntax = rf"(?: {csp_directive} (?: {rfc9110.OWS} ; (?: {rfc9110.OWS} {csp_directive} )? )* )"
    category = categories.SECURITY
    deprecated = False
    report_only_string = ""
    report_only_text = ""

    def __init__(self, wire_name: str, message: ResponseLinterProtocol) -> None:
        super().__init__(wire_name, message)
        self._deferred_notes: List[NoteArgsType] = []
        self._parent_note: Optional[Note] = None

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

        if not parsed_directives:
            raise ValueError("no directives")

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
            self._parent_note = parent
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

                tokens = value.lower().split()

                if name in ["default-src", "script-src", "style-src", "object-src"]:
                    if "*" in tokens:
                        wide_open_directives.append(name)

                if "'unsafe-inline'" in tokens:
                    unsafe_inline_directives.append(name)
                if "'unsafe-eval'" in tokens:
                    unsafe_eval_directives.append(name)
                if name in FETCH_DIRECTIVES and any(token.startswith("http:") for token in tokens):
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

    def post_check(self, add_note: AddNoteMethodType) -> None:
        # evaluate() sets the parent note whenever there is a value.
        if not self.value or self._parent_note is None:
            return

        known_endpoints = known_reporting_endpoints(self.message)

        for parsed_directives in self.value:
            for name, value in parsed_directives.items():
                if name != "report-to":
                    continue
                if value in known_endpoints:
                    continue

                self._parent_note.add_child(
                    CSP_REPORT_TO_MISSING,
                    endpoint=value,
                    report_only_text=self.report_only_text,
                )

    def _make_list(self, items: list[str]) -> MarkdownSafe:
        safe = [inline_safe(item) for item in items]
        return MarkdownSafe("\n".join(f"* `{item}`" for item in safe))


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
    _summary = "The report-to name '%(endpoint)s' doesn't match a Reporting-Endpoints entry."
    _text = """\
The `report-to` directive in [Content Security Policy](https://www.w3.org/TR/CSP3/)
names a reporting endpoint. The Reporting API matches that name against the entries in the
`Reporting-Endpoints` header, and none has this name.

The specification does not use legacy `Report-To` groups for this, so a group with this name in a
`Report-To` header does not satisfy it.%(report_only_text)s"""


class CSPTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = [{"default-src": "'self'", "script-src": "'unsafe-inline'"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]


class CSPMultipleTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'", b"script-src 'unsafe-eval'"]
    expected_out = [{"default-src": "'self'"}, {"script-src": "'unsafe-eval'"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_EVAL]


class CSPDuplicateTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; default-src 'none'"]
    expected_out = [{"default-src": "'self'"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_DUPLICATE_DIRECTIVE]


class CSPReportUriTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"report-uri /csp-report"]
    expected_out = [{"report-uri": "/csp-report"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_DEPRECATED_REPORT_URI]


class CSPWideOpenTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src *"]
    expected_out = [{"script-src": "*"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_WIDE_OPEN]


class CSPTrailingSemiTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"default-src 'self'; script-src 'self';"]
    expected_out = [{"default-src": "'self'", "script-src": "'self'"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY]


class CSPReportToTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"sort-src 'self'; report-to endpoint"]
    expected_out = [{"sort-src": "'self'", "report-to": "endpoint"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CSPReportToMissingTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'self'; report-to endpoint"]
    expected_out = [{"script-src": "'self'", "report-to": "endpoint"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_REPORT_TO_MISSING]


class CSPReportToMismatchTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'self'; report-to endpoint"]
    expected_out = [{"script-src": "'self'", "report-to": "endpoint"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_REPORT_TO_MISSING]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'endpoint-2="https://example.com"')])


class CSPKeywordCaseTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'UNSAFE-INLINE' 'Unsafe-Eval'"]
    expected_out = [{"script-src": "'UNSAFE-INLINE' 'Unsafe-Eval'"}]
    expected_notes: NoteClassListType = [
        CONTENT_SECURITY_POLICY,
        CSP_UNSAFE_INLINE,
        CSP_UNSAFE_EVAL,
    ]


class CSPDefaultSrcWideOpenTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"default-src *"]
    expected_out = [{"default-src": "*"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_WIDE_OPEN]


class CSPHttpSchemeTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src 'self' http:"]
    expected_out = [{"script-src": "'self' http:"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_HTTP_URI]


class CSPHttpHostSourceTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src HTTP://cdn.example.com"]
    expected_out = [{"script-src": "HTTP://cdn.example.com"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_HTTP_URI]


class CSPHttpImgSrcTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"img-src http://img.example.com; connect-src http:; default-src http:"]
    expected_out = [
        {
            "img-src": "http://img.example.com",
            "connect-src": "http:",
            "default-src": "http:",
        }
    ]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_HTTP_URI]


class CSPHttpNonFetchDirectivesTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [
        b"frame-ancestors http://x.example.com; form-action http://x.example.com; "
        b"base-uri http:; navigate-to http://x.example.com"
    ]
    expected_out = [
        {
            "frame-ancestors": "http://x.example.com",
            "form-action": "http://x.example.com",
            "base-uri": "http:",
            "navigate-to": "http://x.example.com",
        }
    ]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY]


class CSPHttpsHostSourceTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b"script-src https://cdn.example.com; report-uri http://example.com/r"]
    expected_out = [{"script-src": "https://cdn.example.com", "report-uri": "http://example.com/r"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_DEPRECATED_REPORT_URI]


class CSPEmptyDirectivesTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy"
    inputs = [b";;;"]
    expected_out = []
    expected_notes: NoteClassListType = [BAD_SYNTAX]
