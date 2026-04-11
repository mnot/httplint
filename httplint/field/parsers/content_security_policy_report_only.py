from httplint.field.parsers.content_security_policy import (
    CONTENT_SECURITY_POLICY,
    CSP_UNSAFE_INLINE,
    content_security_policy,
)
from httplint.field.tests import FieldTest
from httplint.types import (
    NoteClassListType,
    ResponseLinterProtocol,
)


class content_security_policy_report_only(content_security_policy):
    canonical_name = "Content-Security-Policy-Report-Only"
    description = """\
The `Content-Security-Policy-Report-Only` response header allows web site administrators to monitor
the effects of a content security policy without enforcing it."""
    reference = "https://www.w3.org/TR/CSP3/"
    deprecated = False
    report_only_string = " for reporting only"
    report_only_text = "\n\nBrowsers will only report violations of this policy, not enforce it."


class CSPROTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Security-Policy-Report-Only"
    inputs = [b"default-src 'self'; script-src 'unsafe-inline'"]
    expected_out = [{"default-src": "'self'", "script-src": "'unsafe-inline'"}]
    expected_notes: NoteClassListType = [CONTENT_SECURITY_POLICY, CSP_UNSAFE_INLINE]
