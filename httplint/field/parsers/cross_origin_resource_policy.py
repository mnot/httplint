from typing import Any

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class cross_origin_resource_policy(HttpField):
    canonical_name = "Cross-Origin-Resource-Policy"
    description = """\
The `Cross-Origin-Resource-Policy` header field allows a resource to indicate whether it can be
loaded by a cross-origin document."""
    reference = "https://fetch.spec.whatwg.org/#cross-origin-resource-policy-header"
    syntax = False  # Not a Structured Field in the strict sense, but uses token
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = False  # It's a simple string/token

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value in ["same-origin", "same-site", "cross-origin"]:
            add_note(CROSS_ORIGIN_RESOURCE_POLICY, value=self.value)
        else:
            add_note(CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE, value=self.value)


class CROSS_ORIGIN_RESOURCE_POLICY(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "Cross-Origin-Resource-Policy is set to '%(value)s'."
    _text = """\
The `Cross-Origin-Resource-Policy` header controls whether the resource can be loaded by a
cross-origin document.
"""


class CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Cross-Origin-Resource-Policy has an invalid value '%(value)s'."
    _text = """\
The `Cross-Origin-Resource-Policy` header must be one of `same-origin`, `same-site`, or
`cross-origin`.
"""


class CrossOriginResourcePolicySameOriginTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"same-origin"]
    expected_out = "same-origin"
    expected_notes = [CROSS_ORIGIN_RESOURCE_POLICY]


class CrossOriginResourcePolicySameSiteTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"same-site"]
    expected_out = "same-site"
    expected_notes = [CROSS_ORIGIN_RESOURCE_POLICY]


class CrossOriginResourcePolicyCrossOriginTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"cross-origin"]
    expected_out = "cross-origin"
    expected_notes = [CROSS_ORIGIN_RESOURCE_POLICY]


class CrossOriginResourcePolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"foo"]
    expected_out = "foo"
    expected_notes = [CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE]
