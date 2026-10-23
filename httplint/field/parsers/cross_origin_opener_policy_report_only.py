from typing import Any

from http_sf import Token

from httplint.field.parsers.cross_origin_opener_policy import (
    COOP_NOOPENER_ALLOW_POPUPS,
    COOP_SAME_ORIGIN,
    CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
    cross_origin_opener_policy,
)
from httplint.field.tests import FieldTest
from httplint.field.token_policy_field import POLICY_REPORT_TO_NOT_STRING
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.types import (
    NoteClassListType,
    ResponseLinterProtocol,
)


class COOP_REPORT_ONLY_DUPLICATE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "This response has both enforcing and report-only COOP headers."
    _text = """\
A response should not have both `Cross-Origin-Opener-Policy` and
`Cross-Origin-Opener-Policy-Report-Only` headers. The report-only header will be ignored."""


class cross_origin_opener_policy_report_only(cross_origin_opener_policy):
    canonical_name = "Cross-Origin-Opener-Policy-Report-Only"
    description = """\
The `Cross-Origin-Opener-Policy-Report-Only` header field allows a document to report on
potential violations of its Cross-Origin Opener Policy without enforcing them."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
    enforcing_name = "cross-origin-opener-policy"
    report_only_duplicate_note = COOP_REPORT_ONLY_DUPLICATE
    report_only_string = " (for reporting only)"
    report_only_text = MarkdownSafe(
        "\n\nBrowsers will only report violations of this policy, not enforce it."
    )


class CrossOriginOpenerPolicyReportOnlySameOriginTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN]


class CrossOriginOpenerPolicyReportOnlyBadValueTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes: NoteClassListType = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]


class CrossOriginOpenerPolicyReportOnlyReportToTokenTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"same-origin; report-to=endpoint"]
    expected_out: Any = (Token("same-origin"), {"report-to": Token("endpoint")})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, POLICY_REPORT_TO_NOT_STRING]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginOpenerPolicyReportOnlyNoopenerAllowPopupsTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"noopener-allow-popups"]
    expected_out: Any = (Token("noopener-allow-popups"), {})
    expected_notes: NoteClassListType = [COOP_NOOPENER_ALLOW_POPUPS]
