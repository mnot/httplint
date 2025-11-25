from httplint.field.tests import FieldTest
from httplint.field.parsers.content_security_policy import (
    content_security_policy,
    CONTENT_SECURITY_POLICY,
    CSP_UNSAFE_INLINE,
)
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class content_security_policy_report_only(content_security_policy):
    canonical_name = "Content-Security-Policy-Report-Only"
    description = """\
The `Content-Security-Policy-Report-Only` response header allows web site administrators to monitor
the effects of a content security policy without enforcing it."""
    reference = "https://www.w3.org/TR/CSP3/"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    report_only_string = " for reporting only"
    report_only_text = (
        "\n\nBrowsers will only report violations of this policy, not enforce it."
    )

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "content-security-policy" in self.message.headers.handlers:
            add_note(CSP_REPORT_ONLY_DUPLICATE)
        super().evaluate(add_note)


class CSP_REPORT_ONLY_DUPLICATE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "%(message)s has both enforcing and report-only CSP headers."
    _text = """\
A response should not have both `Content-Security-Policy` and
`Content-Security-Policy-Report-Only` headers. The report-only header will be ignored."""


class CSPROTest(FieldTest):
    name = "Content-Security-Policy-Report-Only"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = ["default-src 'self'; script-src 'unsafe-inline'"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]
