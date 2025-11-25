from typing import Any
from http_sf import Token

from httplint.field.tests import FieldTest
from httplint.field.parsers.cross_origin_opener_policy import (
    cross_origin_opener_policy,
    CROSS_ORIGIN_OPENER_POLICY,
    CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
)


class cross_origin_opener_policy_report_only(cross_origin_opener_policy):
    canonical_name = "Cross-Origin-Opener-Policy-Report-Only"
    description = """\
The `Cross-Origin-Opener-Policy-Report-Only` header field allows a document to report on
potential violations of its Cross-Origin Opener Policy without enforcing them."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
    report_only_string = " for reporting only"


class CrossOriginOpenerPolicyReportOnlySameOriginTest(FieldTest):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY]


class CrossOriginOpenerPolicyReportOnlyBadValueTest(FieldTest):
    name = "Cross-Origin-Opener-Policy-Report-Only"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]
