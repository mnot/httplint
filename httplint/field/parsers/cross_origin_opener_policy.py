from typing import Any
from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


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
