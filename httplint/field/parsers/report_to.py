from typing import Any
import json

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class report_to(HttpField):
    canonical_name = "Report-To"
    description = """\
The `Report-To` header field configures the browser to send reports to specified endpoints.
It is part of the legacy Reporting API."""
    reference = "https://w3c.github.io/reporting/#header"
    syntax = False  # JSON
    list_header = False  # JSON array
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        try:
            return json.loads(field_value)
        except json.JSONDecodeError as e:
            add_note(BAD_JSON, error=str(e))
            raise ValueError from e

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value is None:
            return

        if not isinstance(self.value, list):
            add_note(REPORT_TO_BAD_STRUCTURE)
            return

        for group in self.value:
            if not isinstance(group, dict):
                add_note(REPORT_TO_BAD_STRUCTURE)
                continue

            # max_age is required
            if "max_age" not in group:
                add_note(REPORT_TO_MISSING_KEY, key="max_age")
            elif not isinstance(group["max_age"], int):
                add_note(REPORT_TO_BAD_TYPE, key="max_age", expected="integer")

            # endpoints is required
            if "endpoints" not in group:
                add_note(REPORT_TO_MISSING_KEY, key="endpoints")
            elif not isinstance(group["endpoints"], list):
                add_note(REPORT_TO_BAD_TYPE, key="endpoints", expected="list")
            else:
                for endpoint in group["endpoints"]:
                    if not isinstance(endpoint, dict):
                        add_note(
                            REPORT_TO_BAD_STRUCTURE,
                            details="Endpoints must be objects.",
                        )
                        continue
                    if "url" not in endpoint:
                        add_note(REPORT_TO_MISSING_KEY, key="endpoints[].url")
                    elif not isinstance(endpoint["url"], str):
                        add_note(
                            REPORT_TO_BAD_TYPE, key="endpoints[].url", expected="string"
                        )


class BAD_JSON(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Report-To header value is not valid JSON."
    _text = """\
The `Report-To` header value must be valid JSON.

The JSON parsing error was: %(error)s
"""


class REPORT_TO_BAD_STRUCTURE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Report-To header value has an invalid structure."
    _text = """\
The `Report-To` header should be a list of objects.
"""


class REPORT_TO_MISSING_KEY(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Report-To header value is missing the '%(key)s' key."
    _text = """\
The `%(key)s` key is required in `Report-To` objects."""


class REPORT_TO_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Report-To header has an invalid type for '%(key)s'."
    _text = """\
The `%(key)s` key must be of type %(expected)s."""


class ReportToTest(FieldTest):
    name = "Report-To"
    inputs = [
        b'[{"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}]'
    ]
    expected_out = [
        {"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}
    ]
    expected_notes = []


class ReportToListTest(FieldTest):
    name = "Report-To"
    inputs = [
        b'[{"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}]'
    ]
    expected_out = [
        {"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}
    ]
    expected_notes = []


class ReportToMissingMaxAgeTest(FieldTest):
    name = "Report-To"
    inputs = [b'[{"endpoints": [{"url": "https://a.com"}]}]']
    expected_out = [{"endpoints": [{"url": "https://a.com"}]}]
    expected_notes = [REPORT_TO_MISSING_KEY]


class ReportToBadJsonTest(FieldTest):
    name = "Report-To"
    inputs = [b'[{unquoted: "keys"}]']
    expected_out = None
    expected_notes = [BAD_JSON]
