from httplint.field.json_field import JsonField, BAD_JSON
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


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


class NelBadJsonTest(FieldTest):
    name = "NEL"
    inputs = [b"{unquoted: key}"]
    expected_out = None
    expected_notes = [BAD_JSON]
