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

    report_only_text = ""

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value == "same-origin":
            add_note(CORP_SAME_ORIGIN, report_only_text=self.report_only_text)
        elif self.value == "same-site":
            add_note(CORP_SAME_SITE, report_only_text=self.report_only_text)
        elif self.value == "cross-origin":
            add_note(CORP_CROSS_ORIGIN, report_only_text=self.report_only_text)
        else:
            add_note(CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE, value=self.value)


class CORP_SAME_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = (
        "This response is only available for reading to requests from the same origin."
    )
    _text = """\
The `same-origin`
[Cross-Origin Resource Policy](https://fetch.spec.whatwg.org/#cross-origin-resource-policy-header)
prevents the resource from being read by any cross-origin document 
in supporting browsers.%(report_only_text)s"""


class CORP_SAME_SITE(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "This response is available for reading to requests from the same site."
    _text = """\
The `same-site`
[Cross-Origin Resource Policy](https://fetch.spec.whatwg.org/#cross-origin-resource-policy-header)
allows the resource to be read by documents from the same site, but
prevents it from being read by cross-site documents in supporting browsers.%(report_only_text)s"""


class CORP_CROSS_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "This response is available for reading to requests from all origins."
    _text = """\
The `cross-origin`
[Cross-Origin Resource Policy](https://fetch.spec.whatwg.org/#cross-origin-resource-policy-header)
allows the resource to be read by any document in supporting browsers, regardless of its 
origin.%(report_only_text)s"""


class CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Cross-Origin-Resource-Policy has an invalid value."
    _text = """\
`%(value)s` is not a valid value for the `Cross-Origin-Resource-Policy` header;
it must be one of `same-origin`, `same-site`, or `cross-origin`.
"""


class CrossOriginResourcePolicySameOriginTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"same-origin"]
    expected_out = "same-origin"
    expected_notes = [CORP_SAME_ORIGIN]


class CrossOriginResourcePolicySameSiteTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"same-site"]
    expected_out = "same-site"
    expected_notes = [CORP_SAME_SITE]


class CrossOriginResourcePolicyCrossOriginTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"cross-origin"]
    expected_out = "cross-origin"
    expected_notes = [CORP_CROSS_ORIGIN]


class CrossOriginResourcePolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Resource-Policy"
    inputs = [b"foo"]
    expected_out = "foo"
    expected_notes = [CROSS_ORIGIN_RESOURCE_POLICY_BAD_VALUE]
