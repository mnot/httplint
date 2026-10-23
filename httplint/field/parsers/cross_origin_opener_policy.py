from typing import Any

from http_sf import Token

from httplint.field.structured_field import STRUCTURED_FIELD_PARSE_ERROR
from httplint.field.tests import FieldTest
from httplint.field.token_policy_field import (
    POLICY_REPORT_TO_NOT_STRING,
    TokenPolicyField,
)
from httplint.note import Note, categories, levels
from httplint.types import NoteClassListType, ResponseLinterProtocol


class COOP_SAME_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response isolates the browsing context to the same origin%(report_only)s."
    _text = """\
The `same-origin`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
isolates the browsing context, preventing it from sharing a window object
with cross-origin documents in supporting browsers.%(report_only_text)s"""


class COOP_SAME_ORIGIN_ALLOW_POPUPS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response isolates the browsing context but allows popups%(report_only)s."
    _text = """\
The `same-origin-allow-popups`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
isolates the browsing context but maintains a relationship
with popups that it opens, or that opened it, in supporting browsers.%(report_only_text)s"""


class COOP_NOOPENER_ALLOW_POPUPS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response is always placed in a new browsing context group%(report_only)s."
    _text = """\
The `noopener-allow-popups`
[Cross-Origin Opener Policy](https://html.spec.whatwg.org/multipage/origin.html#coop)
forces the document into a new top-level browsing context, severing any opener
relationship with the document that opened it, in supporting browsers.

As the HTML specification notes, this does not create a robust security boundary between
those same-origin documents.%(report_only_text)s"""


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
`noopener-allow-popups`, or `unsafe-none`.
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


class cross_origin_opener_policy(TokenPolicyField):
    canonical_name = "Cross-Origin-Opener-Policy"
    description = """\
The `Cross-Origin-Opener-Policy` header field allows a document to disown its opener, ensuring that
it doesn't have a reference to the opener's window object."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
    policy_notes = {
        "same-origin": COOP_SAME_ORIGIN,
        "same-origin-allow-popups": COOP_SAME_ORIGIN_ALLOW_POPUPS,
        "noopener-allow-popups": COOP_NOOPENER_ALLOW_POPUPS,
        "unsafe-none": COOP_UNSAFE_NONE,
    }
    bad_value_note = CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE
    report_to_missing_note = COOP_REPORT_TO_MISSING


class CrossOriginOpenerPolicySameOriginTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN]


class CrossOriginOpenerPolicySameOriginAllowPopupsTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin-allow-popups"]
    expected_out: Any = (Token("same-origin-allow-popups"), {})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN_ALLOW_POPUPS]


class CrossOriginOpenerPolicyNoopenerAllowPopupsTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"noopener-allow-popups"]
    expected_out: Any = (Token("noopener-allow-popups"), {})
    expected_notes: NoteClassListType = [COOP_NOOPENER_ALLOW_POPUPS]


class CrossOriginOpenerPolicyUnsafeNoneTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"unsafe-none"]
    expected_out: Any = (Token("unsafe-none"), {})
    expected_notes: NoteClassListType = [COOP_UNSAFE_NONE]


class CrossOriginOpenerPolicyBadValueTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes: NoteClassListType = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]


class CrossOriginOpenerPolicyReportToTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b'same-origin; report-to="endpoint"']
    expected_out: Any = (Token("same-origin"), {"report-to": "endpoint"})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginOpenerPolicyReportToMissingTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b'same-origin; report-to="endpoint"']
    expected_out: Any = (Token("same-origin"), {"report-to": "endpoint"})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, COOP_REPORT_TO_MISSING]


class CrossOriginOpenerPolicyReportToTokenTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to=endpoint"]
    expected_out: Any = (Token("same-origin"), {"report-to": Token("endpoint")})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, POLICY_REPORT_TO_NOT_STRING]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginOpenerPolicyReportToIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to=1"]
    expected_out: Any = (Token("same-origin"), {"report-to": 1})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, POLICY_REPORT_TO_NOT_STRING]


class CrossOriginOpenerPolicyReportToBinaryTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to=:AAAA:"]
    expected_out: Any = (Token("same-origin"), {"report-to": b"\x00\x00\x00"})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, POLICY_REPORT_TO_NOT_STRING]


class CrossOriginOpenerPolicyReportToBooleanTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin; report-to"]
    expected_out: Any = (Token("same-origin"), {"report-to": True})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, POLICY_REPORT_TO_NOT_STRING]


class CrossOriginOpenerPolicyUnparseableTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin;;"]
    expected_out: Any = None
    expected_notes: NoteClassListType = [STRUCTURED_FIELD_PARSE_ERROR]


class CrossOriginOpenerPolicyReportToEmptyTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b'same-origin; report-to=""']
    expected_out: Any = (Token("same-origin"), {"report-to": ""})
    expected_notes: NoteClassListType = [COOP_SAME_ORIGIN, COOP_REPORT_TO_MISSING]
