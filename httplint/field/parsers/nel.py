from typing import Any, List, Set

from httplint.field import FIELD_DEPRECATED
from httplint.field.json_field import BAD_JSON, JsonField
from httplint.field.parsers.report_to import REPORT_TO_MISSING_KEY
from httplint.field.parsers.reporting_endpoints import (
    BAD_REPORTING_ENDPOINT_URL,
    ENDPOINT_NOT_SECURE,
    endpoint_problem,
)
from httplint.field.reporting import known_reporting_endpoints
from httplint.field.sf_helpers import is_integer, is_number
from httplint.field.tests import FieldTest
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)
from httplint.util import inline_safe


def _valid_reporting_endpoints(field_value: Any, base_uri: str) -> Set[str]:
    """Names of reporting endpoints that are well-formed and use a secure scheme."""
    valid: Set[str] = set()
    for name, item in field_value.items():
        url = item[0]
        if not isinstance(url, str):
            continue
        if endpoint_problem(base_uri, url) is None:
            valid.add(name)
    return valid


def _usable_report_to_groups(message: ResponseLinterProtocol) -> Set[str]:
    """
    Names of Report-To groups with at least one endpoint that has a well-formed URL and a
    secure scheme.
    """
    usable: Set[str] = set()
    report_to_value = message.headers.parsed.get("report-to")
    if not isinstance(report_to_value, list):
        return usable
    for group in report_to_value:
        if not isinstance(group, dict):
            continue
        name = group.get("group", "default")
        endpoints = group.get("endpoints")
        if not isinstance(name, str) or not isinstance(endpoints, list):
            continue
        for endpoint in endpoints:
            url = endpoint.get("url") if isinstance(endpoint, dict) else None
            if isinstance(url, str) and endpoint_problem(message.base_uri, url) is None:
                usable.add(name)
                break
    return usable


class nel(JsonField[ResponseLinterProtocol]):
    canonical_name = "NEL"
    description = """\
The `NEL` header field configures Network Error Logging policies. 
It allows websites to declare that they want to receive reports about network errors."""
    reference = "https://w3c.github.io/network-error-logging/#nel-header-field"
    deprecated = False

    def __init__(self, wire_name: str, message: ResponseLinterProtocol) -> None:
        super().__init__(wire_name, message)
        self._clean_policies: List[bool] = []

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value is None:
            return

        # Spec: "User agent MUST only process the first valid policy..."
        # We process all of them for validation purposes
        for policy in self.value:
            if not isinstance(policy, dict):
                add_note(NEL_BAD_STRUCTURE)
                self._clean_policies.append(False)
                continue

            clean = True

            # report_to
            if "report_to" not in policy:
                add_note(NEL_MISSING_KEY, key="report_to")
                clean = False
            elif not isinstance(policy["report_to"], str):
                add_note(NEL_BAD_TYPE, key="report_to", expected="string")
                clean = False

            # max_age needed
            # "If `max_age` member is missing ... user agent MUST ignore the policy."
            if "max_age" not in policy:
                add_note(NEL_MISSING_KEY, key="max_age")
                clean = False
            elif not is_integer(policy["max_age"]):
                add_note(NEL_BAD_TYPE, key="max_age", expected="integer")
                clean = False
            elif policy["max_age"] < 0:
                add_note(
                    NEL_BAD_VALUE,
                    key="max_age",
                    details="it must not be negative",
                )
                clean = False

            # optional members
            if "include_subdomains" in policy and not isinstance(
                policy["include_subdomains"], bool
            ):
                add_note(NEL_BAD_TYPE, key="include_subdomains", expected="boolean")
                clean = False

            if "success_fraction" in policy:
                if not is_number(policy["success_fraction"]):
                    add_note(NEL_BAD_TYPE, key="success_fraction", expected="number")
                    clean = False
                elif not 0.0 <= policy["success_fraction"] <= 1.0:
                    add_note(
                        NEL_BAD_VALUE,
                        key="success_fraction",
                        details="it must be between 0.0 and 1.0",
                    )
                    clean = False

            if "failure_fraction" in policy:
                if not is_number(policy["failure_fraction"]):
                    add_note(NEL_BAD_TYPE, key="failure_fraction", expected="number")
                    clean = False
                elif not 0.0 <= policy["failure_fraction"] <= 1.0:
                    add_note(
                        NEL_BAD_VALUE,
                        key="failure_fraction",
                        details="it must be between 0.0 and 1.0",
                    )
                    clean = False

            self._clean_policies.append(clean)

    def post_check(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        # Browsers that implement NEL take its endpoints from Report-To groups.
        known_endpoints = known_reporting_endpoints(self.message, include_report_to=True)
        reporting_endpoints_field = self.message.headers.parsed.get("reporting-endpoints")
        valid_endpoints = _usable_report_to_groups(self.message)
        if reporting_endpoints_field:
            valid_endpoints |= _valid_reporting_endpoints(
                reporting_endpoints_field, self.message.base_uri
            )

        resolved_endpoints = []
        for idx, policy in enumerate(self.value):
            if not isinstance(policy, dict):
                continue
            report_to = policy.get("report_to")
            if report_to and isinstance(report_to, str):
                if report_to not in known_endpoints:
                    add_note(NEL_REPORT_TO_MISSING, key="report_to", value=report_to)
                elif report_to in valid_endpoints:
                    if self._clean_policies[idx]:
                        resolved_endpoints.append(report_to)
                elif not (reporting_endpoints_field and report_to in reporting_endpoints_field):
                    # A Report-To group (a Reporting-Endpoints problem has its own note).
                    add_note(NEL_REPORT_TO_GROUP_UNUSABLE, value=report_to)

        if resolved_endpoints:
            add_note(
                NEL_CONFIGURED,
                endpoints=MarkdownSafe(
                    ", ".join(f"`{inline_safe(e)}`" for e in resolved_endpoints)
                ),
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
The `%(key)s` key has an invalid value; %(details)s."""


class NEL_CONFIGURED(Note):
    category = categories.GENERAL
    level = levels.GOOD
    _summary = "Network Error Logging is configured for this response."
    _text = """\
The `NEL` header configures
[Network Error Logging](https://w3c.github.io/network-error-logging/), which instructs the browser
to report network-level errors (DNS, TCP, TLS, and HTTP failures) to the reporting endpoint(s):
%(endpoints)s.

This supports observability of failures that would otherwise be invisible to the server."""


class NEL_REPORT_TO_MISSING(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The reporting endpoint '%(value)s' is not defined."
    _text = """\
The `report_to` member in the [Network Error Logging](https://w3c.github.io/network-error-logging/)
policy specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header or a group in the `Report-To` header."""


class NEL_REPORT_TO_GROUP_UNUSABLE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Report-To group '%(value)s' has no usable endpoint."
    _text = """\
The `report_to` member in the [Network Error Logging](https://w3c.github.io/network-error-logging/)
policy names a group in the `Report-To` header, but none of the group's endpoints has a
well-formed URL with a secure scheme, so browsers may not deliver reports to it."""


class NelTest(FieldTest[ResponseLinterProtocol]):
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
    expected_notes: NoteClassListType = [NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="https://example.com/reports"')])


class NelMultiLineTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [
        b'{"report_to": "group1", "max_age": 2592000}',
        b'{"report_to": "group2", "max_age": 3600}',
    ]
    expected_out = [
        {"report_to": "group1", "max_age": 2592000},
        {"report_to": "group2", "max_age": 3600},
    ]
    expected_notes: NoteClassListType = [NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [
                (
                    b"Reporting-Endpoints",
                    b'group1="https://example.com/1", group2="https://example.com/2"',
                )
            ]
        )


class NelMissingReportToTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"max_age": 100}']
    expected_out = [{"max_age": 100}]
    expected_notes: NoteClassListType = [NEL_MISSING_KEY]


class NelBadFractionTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "a", "max_age": 1, "success_fraction": 1.5}']
    expected_out = [{"report_to": "a", "max_age": 1, "success_fraction": 1.5}]
    expected_notes: NoteClassListType = [NEL_BAD_VALUE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'a="https://example.com/reports"')])


class NelBadJsonTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b"{unquoted: key}"]
    expected_out = None
    expected_out = None
    expected_notes: NoteClassListType = [BAD_JSON]


class NelReportToTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes: NoteClassListType = [NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="https://example.com/reports"')])


class NelReportToMissingTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes: NoteClassListType = [NEL_REPORT_TO_MISSING]


class NelReportToInsecureTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes: NoteClassListType = [ENDPOINT_NOT_SECURE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="http://example.com/reports"')])


class NelReportToBadURLTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "group1", "max_age": 100}']
    expected_out = [{"report_to": "group1", "max_age": 100}]
    expected_notes: NoteClassListType = [BAD_REPORTING_ENDPOINT_URL]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'group1="http://["')])


def _report_to_header(group: str, *urls: str) -> bytes:
    endpoints = ", ".join(f'{{"url": "{url}"}}' for url in urls)
    return f'{{"group": "{group}", "max_age": 10, "endpoints": [{endpoints}]}}'.encode()


class NelReportToGroupTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [
                (
                    b"Report-To",
                    _report_to_header("g", "https://example.com/r"),
                )
            ]
        )


class NelReportToDefaultGroupTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "default", "max_age": 1}']
    expected_out = [{"report_to": "default", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Report-To", b'{"max_age": 10, "endpoints": [{"url": "https://example.com/r"}]}')]
        )


class NelReportToOtherGroupTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_REPORT_TO_MISSING]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [
                (
                    b"Report-To",
                    _report_to_header("other", "https://example.com/r"),
                )
            ]
        )


class NelReportToGroupInsecureTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_REPORT_TO_GROUP_UNUSABLE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [
                (
                    b"Report-To",
                    _report_to_header("g", "http://example.com/r"),
                )
            ]
        )


class NelReportToGroupNoEndpointsTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [
        FIELD_DEPRECATED,
        REPORT_TO_MISSING_KEY,
        NEL_REPORT_TO_GROUP_UNUSABLE,
    ]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Report-To", b'{"group": "g", "max_age": 10}')])


class NelReportToGroupBadURLTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_REPORT_TO_GROUP_UNUSABLE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Report-To", _report_to_header("g", "http://["))])


class NelReportToGroupOneUsableTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1}']
    expected_out = [{"report_to": "g", "max_age": 1}]
    expected_notes: NoteClassListType = [FIELD_DEPRECATED, NEL_CONFIGURED]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [
                (
                    b"Report-To",
                    _report_to_header("g", "http://example.com/r", "https://example.com/r"),
                )
            ]
        )


class NelBooleanMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": true}']
    expected_out = [{"report_to": "g", "max_age": True}]
    expected_notes: NoteClassListType = [NEL_BAD_TYPE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'g="https://example.com/reports"')])


class NelNegativeMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": -1}']
    expected_out = [{"report_to": "g", "max_age": -1}]
    expected_notes: NoteClassListType = [NEL_BAD_VALUE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'g="https://example.com/reports"')])


class NelBooleanFractionTest(FieldTest[ResponseLinterProtocol]):
    name = "NEL"
    inputs = [b'{"report_to": "g", "max_age": 1, "success_fraction": true}']
    expected_out = [{"report_to": "g", "max_age": 1, "success_fraction": True}]
    expected_notes: NoteClassListType = [NEL_BAD_TYPE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process([(b"Reporting-Endpoints", b'g="https://example.com/reports"')])
