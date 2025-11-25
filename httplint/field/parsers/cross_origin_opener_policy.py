from typing import Any
from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.field.utils import check_sf_item_token
from httplint.types import AddNoteMethodType


class cross_origin_opener_policy(HttpField):
    canonical_name = "Cross-Origin-Opener-Policy"
    description = """\
The `Cross-Origin-Opener-Policy` header field allows a document to disown its opener, ensuring that
it doesn't have a reference to the opener's window object."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coop"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "item"
    report_only_string = ""

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_sf_item_token(
            self.value,
            [
                Token("same-origin"),
                Token("same-origin-allow-popups"),
                Token("unsafe-none"),
            ],
            add_note,
            CROSS_ORIGIN_OPENER_POLICY,
            CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE,
            report_only=self.report_only_string,
        )


class CROSS_ORIGIN_OPENER_POLICY(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "%(message)s sets a cross-origin opener policy%(report_only)s."
    _text = """\
The `%(field_name)s` header controls whether the document shares a browsing context
group with other documents.
"""


class CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "%(field_name)s's %(message)s has an invalid value."
    _text = """\
The `%(field_name)s` header must be one of `same-origin`, `same-origin-allow-popups`,
or `unsafe-none`.
"""


class CrossOriginOpenerPolicySameOriginTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin"]
    expected_out: Any = (Token("same-origin"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY]


class CrossOriginOpenerPolicySameOriginAllowPopupsTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"same-origin-allow-popups"]
    expected_out: Any = (Token("same-origin-allow-popups"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY]


class CrossOriginOpenerPolicyUnsafeNoneTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"unsafe-none"]
    expected_out: Any = (Token("unsafe-none"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY]


class CrossOriginOpenerPolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Opener-Policy"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_OPENER_POLICY_BAD_VALUE]
