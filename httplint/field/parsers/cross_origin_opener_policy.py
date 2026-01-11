from typing import Any, TYPE_CHECKING
from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class cross_origin_opener_policy(StructuredField):
    canonical_name = "Cross-Origin-Opener-Policy"
    description = """\
The `Cross-Origin-Opener-Policy` header field allows a document to disown its opener, ensuring that
it doesn't have a reference to the opener's window object."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
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
                if val == "same-origin":
                    add_note(
                        COOP_SAME_ORIGIN,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                elif val == "same-origin-allow-popups":
                    add_note(
                        COOP_SAME_ORIGIN_ALLOW_POPUPS,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                elif val == "unsafe-none":
                    add_note(
                        COOP_UNSAFE_NONE,
                        report_only=self.report_only_string,
                        report_only_text=self.report_only_text,
                    )
                else:
                    add_note(
                        CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
                        value=val,
                        report_only=self.report_only_string,
                    )
            else:
                add_note(
                    CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
                    value=val,
                    report_only=self.report_only_string,
                )
        else:
            add_note(
                CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
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
                COOP_REPORT_TO_MISSING,
                endpoint=report_to,
                report_only=self.report_only_string,
            )


class COOP_SAME_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = (
        "This response isolates the browsing context to the same origin%(report_only)s."
    )
    _text = """\
The `same-origin`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
isolates the browsing context, preventing it from sharing a window object
with cross-origin documents in supporting browsers.%(report_only_text)s"""


class COOP_SAME_ORIGIN_ALLOW_POPUPS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = (
        "This response isolates the browsing context but allows popups%(report_only)s."
    )
    _text = """\
The `same-origin-allow-popups`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
isolates the browsing context but maintains a relationship
with popups that it opens, or that opened it, in supporting browsers.%(report_only_text)s"""


class COOP_UNSAFE_NONE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "This response allows sharing the browsing context "
        "with cross-origin documents%(report_only)s."
    )
    _text = """\
The `unsafe-none`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
is the default behavior in supporting browsers. It allows the document to share a browsing context
group with other documents unless they enforce isolation.%(report_only_text)s"""


class CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "This response's %(field_name)s has an invalid value."
    _text = """\
The `%(field_name)s` header must be one of `same-origin`, `same-origin-allow-popups`,
or `unsafe-none`.
"""


class COOP_REPORT_TO_MISSING(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The report-to endpoint '%(endpoint)s' is not defined%(report_only)s."
    _text = """\
The `report-to` parameter in the
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
header specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header."""


class CrossOriginOpenerPolicySameOriginTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes = [COOP_SAME_ORIGIN]


class CrossOriginOpenerPolicySameOriginAllowPopupsTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin-allow-popups"]
    expected_out: Any = (Token("same-origin-allow-popups"), {})
    expected_notes = [COOP_SAME_ORIGIN_ALLOW_POPUPS]


class CrossOriginOpenerPolicyUnsafeNoneTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"unsafe-none"]
    expected_out: Any = (Token("unsafe-none"), {})
    expected_notes = [COOP_UNSAFE_NONE]


class CrossOriginOpenerPolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]


class CrossOriginOpenerPolicyReportToTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to=endpoint"]
    expected_out: Any = (Token("same-origin"), {"report-to": "endpoint"})
    expected_notes = [COOP_SAME_ORIGIN]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginOpenerPolicyReportToMissingTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to=endpoint"]
    expected_out: Any = (Token("same-origin"), {"report-to": "endpoint"})
    expected_notes = [COOP_SAME_ORIGIN, COOP_REPORT_TO_MISSING]
