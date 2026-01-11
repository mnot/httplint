from typing import Any, TYPE_CHECKING
from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class cross_origin_embedder_policy(StructuredField):
    canonical_name = "Cross-Origin-Embedder-Policy"
    description = """\
The `Cross-Origin-Embedder-Policy` header field prevents a document from loading any cross-origin
resources that don't explicitly grant the document permission (using CORP or CORS)."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coep"
    syntax = False  # Structured Field
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "item"
    report_only_string = ""
    report_only_text = ""

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if isinstance(self.value, tuple):
            val = self.value[0]
            if isinstance(val, Token):
                if val == "require-corp":
                    add_note(
                        COEP_REQUIRE_CORP,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                elif val == "credentialless":
                    add_note(
                        COEP_CREDENTIALLESS,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                elif val == "unsafe-none":
                    add_note(
                        COEP_UNSAFE_NONE,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                else:
                    add_note(
                        CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE,
                        value=val,
                        report_only=self.report_only_string,
                    )
            else:
                add_note(
                    CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE,
                    value=val,
                    report_only=self.report_only_string,
                )
        else:
            add_note(
                CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE,
                value=self.value,
                report_only=self.report_only_string,
            )

    def post_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> None:
        if not self.value or not isinstance(self.value, tuple):
            return

        # self.value is (item, params)
        params = self.value[1]
        report_to = params.get("report-to")
        if not report_to:
            return

        reporting_endpoints_field = message.headers.parsed.get("reporting-endpoints")
        reporting_endpoints = (
            list(reporting_endpoints_field.keys()) if reporting_endpoints_field else []
        )
        known_endpoints = set(reporting_endpoints)

        if report_to not in known_endpoints:
            add_note(
                COEP_REPORT_TO_MISSING,
                endpoint=report_to,
                report_only=self.report_only_string,
            )


class COEP_REQUIRE_CORP(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response requires resources to have a CORP header%(report_only)s."
    _text = """\
The `require-corp`
[Cross Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
requires that all cross-origin resources must explicitly grant permission to be loaded via a
`Cross-Origin-Resource-Policy` header, in supporting browsers.%(report_only_text)s"""


class COEP_CREDENTIALLESS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = (
        "This response loads cross-origin resources without credentials%(report_only)s."
    )
    _text = """\
The `credentialless`
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
allows loading cross-origin resources without explicit permission in supporting browsers, but
requests for them will not include credentials (cookies, client certificates,
etc.).%(report_only_text)s"""


class COEP_UNSAFE_NONE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "This response allows loading cross-origin resources without restriction"
        "%(report_only)s."
    )
    _text = """\
The `unsafe-none`
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
is the default behavior, allowing cross-origin resources to be loaded
without explicit permission in supporting browsers.

This does not provide cross-origin isolation.%(report_only_text)s"""


class CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "This response's %(field_name)s has an invalid value."
    _text = """\
The `%(field_name)s` header must be one of `require-corp`, `credentialless`, or
`unsafe-none`.
"""


class COEP_REPORT_TO_MISSING(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The report-to endpoint '%(endpoint)s' is not defined%(report_only)s."
    _text = """\
The `report-to` parameter in the
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
header specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header."""


class CrossOriginEmbedderPolicyRequireCorpTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp"]
    expected_out: Any = (Token("require-corp"), {})
    expected_notes = [COEP_REQUIRE_CORP]


class CrossOriginEmbedderPolicyCredentiallessTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"credentialless"]
    expected_out: Any = (Token("credentialless"), {})
    expected_notes = [COEP_CREDENTIALLESS]


class CrossOriginEmbedderPolicyUnsafeNoneTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"unsafe-none"]
    expected_out: Any = (Token("unsafe-none"), {})
    expected_notes = [COEP_UNSAFE_NONE]


class CrossOriginEmbedderPolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE]


class CrossOriginEmbedderPolicyReportToTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp; report-to=endpoint"]
    expected_out: Any = (Token("require-corp"), {"report-to": "endpoint"})
    expected_notes = [COEP_REQUIRE_CORP]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginEmbedderPolicyReportToMissingTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp; report-to=endpoint"]
    expected_out: Any = (Token("require-corp"), {"report-to": "endpoint"})
    expected_notes = [COEP_REQUIRE_CORP, COEP_REPORT_TO_MISSING]
