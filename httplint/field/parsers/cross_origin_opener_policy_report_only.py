from typing import Any
from http_sf import Token

from httplint.field.tests import FieldTest
from httplint.field.parsers.cross_origin_opener_policy import (
    cross_origin_opener_policy,
    COOP_SAME_ORIGIN,
    CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
)
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class cross_origin_opener_policy_report_only(cross_origin_opener_policy):
    canonical_name = "Cross-Origin-Opener-Policy-Report-Only"
    description = """\
The `Cross-Origin-Opener-Policy-Report-Only` header field allows a document to report on
potential violations of its Cross-Origin Opener Policy without enforcing them."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
    report_only_string = " (for reporting only)"
    report_only_text = (
        "\n\nBrowsers will only report violations of this policy, not enforce it."
    )

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "cross-origin-opener-policy" in self.message.headers.handlers:
            add_note(COOP_REPORT_ONLY_DUPLICATE)
        super().evaluate(add_note)


class COOP_REPORT_ONLY_DUPLICATE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "This response has both enforcing and report-only COOP headers."
    _text = """\
A response should not have both `Cross-Origin-Opener-Policy` and
`Cross-Origin-Opener-Policy-Report-Only` headers. The report-only header will be ignored."""


class CrossOriginOpenerPolicyReportOnlySameOriginTest(FieldTest):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes = [COOP_SAME_ORIGIN]


class CrossOriginOpenerPolicyReportOnlyBadValueTest(FieldTest):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]
