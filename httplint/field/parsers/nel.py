from typing import Any, List, Set
from urllib.parse import urljoin, urlsplit

from httplint.field.json_field import BAD_JSON, JsonField
from httplint.field.parsers.reporting_endpoints import ENDPOINT_NOT_SECURE
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)


def _valid_reporting_endpoints(field_value: Any, base_uri: str) -> Set[str]:
    """Names of reporting endpoints that are well-formed and use a secure scheme."""
    valid: Set[str] = set()
    for name, item in field_value.items():
        url = item[0]
        if not isinstance(url, str):
            continue
        target = urljoin(base_uri, url)
        scheme = urlsplit(target).scheme.lower()
        if scheme and scheme not in ("https", "wss"):
            continue
        valid.add(name)
    return valid


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
            elif not isinstance(policy["max_age"], int):
                add_note(NEL_BAD_TYPE, key="max_age", expected="integer")
                clean = False

            # optional members
            if "include_subdomains" in policy and not isinstance(
                policy["include_subdomains"], bool
            ):
                add_note(NEL_BAD_TYPE, key="include_subdomains", expected="boolean")
                clean = False

            if "success_fraction" in policy:
                if not isinstance(policy["success_fraction"], (int, float)):
                    add_note(NEL_BAD_TYPE, key="success_fraction", expected="number")
                    clean = False
                elif not 0.0 <= policy["success_fraction"] <= 1.0:
                    add_note(
                        NEL_BAD_VALUE,
                        key="success_fraction",
                        details="itmust be between 0.0 and 1.0",
                    )
                    clean = False

            if "failure_fraction" in policy:
                if not isinstance(policy["failure_fraction"], (int, float)):
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

        reporting_endpoints_field = self.message.headers.parsed.get("reporting-endpoints")
        reporting_endpoints = (
            list(reporting_endpoints_field.keys()) if reporting_endpoints_field else []
        )
        known_endpoints = set(reporting_endpoints)
        valid_endpoints = (
            _valid_reporting_endpoints(reporting_endpoints_field, self.message.base_uri)
            if reporting_endpoints_field
            else set()
        )

        resolved_endpoints = []
        for idx, policy in enumerate(self.value):
            if not isinstance(policy, dict):
                continue
            report_to = policy.get("report_to")
            if report_to and isinstance(report_to, str):
                if report_to not in known_endpoints:
                    add_note(NEL_REPORT_TO_MISSING, key="report_to", value=report_to)
                elif report_to in valid_endpoints and self._clean_policies[idx]:
                    resolved_endpoints.append(report_to)

        if resolved_endpoints:
            add_note(
                NEL_CONFIGURED,
                endpoints=", ".join(f"`{e}`" for e in resolved_endpoints),
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
`Reporting-Endpoints` header."""


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
