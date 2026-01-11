from typing import TYPE_CHECKING

from httplint.field.json_field import JsonField, BAD_JSON
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class nel(JsonField):
    canonical_name = "NEL"
    description = """\
The `NEL` header field configures Network Error Logging policies. 
It allows websites to declare that they want to receive reports about network errors."""
    reference = "https://w3c.github.io/network-error-logging/#nel-header-field"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value is None:
            return

        # Spec: "User agent MUST only process the first valid policy..."
        # We process all of them for validation purposes
        for policy in self.value:
            if not isinstance(policy, dict):
                add_note(NEL_BAD_STRUCTURE)
                continue

            # report_to
            if "report_to" not in policy:
                add_note(NEL_MISSING_KEY, key="report_to")
            elif not isinstance(policy["report_to"], str):
                add_note(NEL_BAD_TYPE, key="report_to", expected="string")

            # max_age needed
            # "If `max_age` member is missing ... user agent MUST ignore the policy."
            if "max_age" not in policy:
                add_note(NEL_MISSING_KEY, key="max_age")
            elif not isinstance(policy["max_age"], int):
                add_note(NEL_BAD_TYPE, key="max_age", expected="integer")

            # optional members
            if "include_subdomains" in policy and not isinstance(
                policy["include_subdomains"], bool
            ):
                add_note(NEL_BAD_TYPE, key="include_subdomains", expected="boolean")

            if "success_fraction" in policy:
                if not isinstance(policy["success_fraction"], (int, float)):
                    add_note(NEL_BAD_TYPE, key="success_fraction", expected="number")
                elif not 0.0 <= policy["success_fraction"] <= 1.0:
                    add_note(
                        NEL_BAD_VALUE,
                        key="success_fraction",
                        details="itmust be between 0.0 and 1.0",
                    )

            if "failure_fraction" in policy:
                if not isinstance(policy["failure_fraction"], (int, float)):
                    add_note(NEL_BAD_TYPE, key="failure_fraction", expected="number")
                elif not 0.0 <= policy["failure_fraction"] <= 1.0:
                    add_note(
                        NEL_BAD_VALUE,
                        key="failure_fraction",
                        details="it must be between 0.0 and 1.0",
                    )

    def post_check(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        reporting_endpoints_field = message.headers.parsed.get("reporting-endpoints")
        reporting_endpoints = (
            list(reporting_endpoints_field.keys()) if reporting_endpoints_field else []
        )
        known_endpoints = set(reporting_endpoints)

        for policy in self.value:
            if not isinstance(policy, dict):
                continue
            report_to = policy.get("report_to")
            if report_to and isinstance(report_to, str):
                if report_to not in known_endpoints:
                    add_note(NEL_REPORT_TO_MISSING, key="report_to", value=report_to)


class NEL_BAD_STRUCTURE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The NEL header has an invalid structure."
    _text = """\
The `NEL` header should be a list of objects.
"""


class NEL_MISSING_KEY(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The NEL policy is missing the '%(key)s' key."
    _text = """\
The `%(key)s` key is required in `NEL` policies."""


class NEL_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The NEL policy has an invalid type for '%(key)s'."
    _text = """\
The `%(key)s` key must be of type %(expected)s."""


class NEL_BAD_VALUE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The NEL policy has an invalid value for '%(key)s'."
    _text = """\
The `%(key)s` key has an invalid value; %(details)s.
Details: %(details)s"""


class NEL_REPORT_TO_MISSING(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The report_to endpoint '%(value)s' is not defined."
    _text = """\
The `report_to` member in the [Network Error Logging](https://w3c.github.io/network-error-logging/)
policy specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header."""


class NelTest(FieldTest):
    name = "NEL"
    inputs = [
        b'{"report_to": "group1", "max_age": 2592000, "include_subdomains": true, '
        b'"success_fraction": 0.5}'
    ]
    expected_out = [
        {
            "report_to": "group1",
            "max_age": 2592000,
            "include_subdomains": True,
            "success_fraction": 0.5,
        }
    ]
    expected_notes = []

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="https://example.com/reports"')])


class NelMultiLineTest(FieldTest):
    name = "NEL"
    inputs = [
        b'{"report_to": "group1", "max_age": 2592000}',
        b'{"report_to": "group2", "max_age": 3600}',
    ]
    expected_out = [
        {"report_to": "group1", "max_age": 2592000},
        {"report_to": "group2", "max_age": 3600},
    ]
    expected_notes = []

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process(
            [
                (
                    b"Reporting-Endpoints",
                    b'group1="https://example.com/1", group2="https://example.com/2"',
                )
            ]
        )


class NelMissingReportToTest(FieldTest):
    name = "NEL"
    inputs = [b'{"max_age": 100}']
    expected_out = [{"max_age": 100}]
    expected_notes = [NEL_MISSING_KEY]


class NelBadFractionTest(FieldTest):
    name = "NEL"
    inputs = [b'{"report_to": "a", "max_age": 1, "success_fraction": 1.5}']
    expected_out = [{"report_to": "a", "max_age": 1, "success_fraction": 1.5}]
    expected_notes = [NEL_BAD_VALUE]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process([(b"Reporting-Endpoints", b'a="https://example.com/reports"')])


class NelBadJsonTest(FieldTest):
    name = "NEL"
    inputs = [b"{unquoted: key}"]
    expected_out = None
    expected_out = None
    expected_notes = [BAD_JSON]


class NelReportToTest(FieldTest):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes = []

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="https://example.com/reports"')])


class NelReportToMissingTest(FieldTest):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes = [NEL_REPORT_TO_MISSING]
