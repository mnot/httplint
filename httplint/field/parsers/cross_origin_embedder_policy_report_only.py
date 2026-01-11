from typing import Any
from http_sf import Token

from httplint.field.tests import FieldTest
from httplint.field.parsers.cross_origin_embedder_policy import (
    cross_origin_embedder_policy,
    COEP_REQUIRE_CORP,
    CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE,
)
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class cross_origin_embedder_policy_report_only(cross_origin_embedder_policy):
    canonical_name = "Cross-Origin-Embedder-Policy-Report-Only"
    description = """\
The `Cross-Origin-Embedder-Policy-Report-Only` header field allows a document to report on
potential violations of its Cross-Origin Embedder Policy without enforcing them."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coep"
    report_only_string = " (for reporting only)"
    report_only_text = "\n\nBrowsers will only report violations of this policy, not enforce it."

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "cross-origin-embedder-policy" in self.message.headers.handlers:
            add_note(COEP_REPORT_ONLY_DUPLICATE)
        super().evaluate(add_note)


class COEP_REPORT_ONLY_DUPLICATE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "This response has both enforcing and report-only COEP headers."
    _text = """\
A response should not have both `Cross-Origin-Embedder-Policy` and
`Cross-Origin-Embedder-Policy-Report-Only` headers. The report-only header will be ignored."""


class CrossOriginEmbedderPolicyReportOnlyRequireCorpTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy-Report-Only"
    inputs = [b"require-corp"]
    expected_out: Any = (Token("require-corp"), {})
    expected_notes = [COEP_REQUIRE_CORP]


class CrossOriginEmbedderPolicyReportOnlyBadValueTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy-Report-Only"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE]
