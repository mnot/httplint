from httplint.field.tests import FieldTest
from httplint.field.parsers.content_security_policy import (
    content_security_policy,
    CONTENT_SECURITY_POLICY,
    CSP_UNSAFE_INLINE,
)


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


class CSPROTest(FieldTest):
    name = "Content-Security-Policy-Report-Only"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = ["default-src 'self'; script-src 'unsafe-inline'"]
    expected_notes = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]
