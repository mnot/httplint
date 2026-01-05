from httplint.field.json_field import JsonField, BAD_JSON
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class report_to(JsonField):
    canonical_name = "Report-To"
    description = """\
The `Report-To` header field configures the browser to send reports to specified endpoints.
It is part of the legacy Reporting API."""
    reference = "https://w3c.github.io/reporting/#header"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value is None:
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
        b'{"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}'
    ]
    expected_out = [
        {"max_age": 10886400, "endpoints": [{"url": "https://example.com/reports"}]}
    ]
    expected_notes = []


class ReportToMultiLineTest(FieldTest):
    name = "Report-To"
    inputs = [
        b'{"group": "a", "max_age": 1, "endpoints": [{"url": "https://a.com"}]}',
        b'{"group": "b", "max_age": 2, "endpoints": [{"url": "https://b.com"}]}',
    ]
    expected_out = [
        {"group": "a", "max_age": 1, "endpoints": [{"url": "https://a.com"}]},
        {"group": "b", "max_age": 2, "endpoints": [{"url": "https://b.com"}]},
    ]
    expected_notes = []


class ReportToMissingMaxAgeTest(FieldTest):
    name = "Report-To"
    inputs = [b'{"endpoints": [{"url": "https://a.com"}]}']
    expected_out = [{"endpoints": [{"url": "https://a.com"}]}]
    expected_notes = [REPORT_TO_MISSING_KEY]


class ReportToBadJsonTest(FieldTest):
    name = "Report-To"
    inputs = [b'{unquoted: "keys"}']
    expected_out = None
    expected_notes = [BAD_JSON]
