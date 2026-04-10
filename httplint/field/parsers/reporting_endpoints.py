from typing import Any
from urllib.parse import urljoin, urlsplit

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFDictionaryType,
)


class reporting_endpoints(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Reporting-Endpoints"
    description = """\
The `Reporting-Endpoints` header field defines one or more reporting endpoints for the Reporting
API."""
    reference = "https://www.w3.org/TR/reporting/#header"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "dictionary"
    value: SFDictionaryType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        for name, item in self.value.items():
            # item is (value, params)
            url = item[0]
            if not isinstance(url, str):
                add_note(
                    BAD_REPORTING_ENDPOINT_SYNTAX,
                    name=name,
                    value=url,
                    found_type=type(url).__name__,
                )
                continue

            target = urljoin(self.message.base_uri, url)
            parsed = urlsplit(target)
            if parsed.scheme and parsed.scheme.lower() not in ["https", "wss"]:
                add_note(ENDPOINT_NOT_SECURE, name=name, url=url)


class ENDPOINT_NOT_SECURE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The %(name)s reporting endpoint is not secure."
    _text = """\
The reporting endpoint `%(name)s` uses an insecure URL (`%(url)s`). Browsers may ignore it."""


class BAD_REPORTING_ENDPOINT_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(name)s reporting endpoint is invalid."
    _text = """\
The reporting endpoint `%(name)s` must be a string URL. Found: %(value)s (type `%(found_type)s`)."""


class ReportingEndpointsTest(FieldTest[ResponseLinterProtocol]):
    name = "Reporting-Endpoints"
    inputs = [b'endpoint="https://example.com/reports"']
    expected_out: Any = {"endpoint": ("https://example.com/reports", {})}


class ReportingEndpointsInsecureTest(FieldTest[ResponseLinterProtocol]):
    name = "Reporting-Endpoints"
    inputs = [b'endpoint="http://example.com/reports"']
    expected_out: Any = {"endpoint": ("http://example.com/reports", {})}
    expected_notes: NoteClassListType = [ENDPOINT_NOT_SECURE]


class ReportingEndpointsBadSyntaxTest(FieldTest[ResponseLinterProtocol]):
    name = "Reporting-Endpoints"
    inputs = [b"endpoint=123"]
    expected_out: Any = {"endpoint": (123, {})}
    expected_notes: NoteClassListType = [BAD_REPORTING_ENDPOINT_SYNTAX]


class ReportingEndpointsRelativeTest(FieldTest[ResponseLinterProtocol]):
    name = "Reporting-Endpoints"
    inputs = [b'endpoint="/reports"']
    expected_out: Any = {"endpoint": ("/reports", {})}
    expected_notes: NoteClassListType = []

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "https://example.com/"


class ReportingEndpointsInsecureBaseTest(FieldTest[ResponseLinterProtocol]):
    name = "Reporting-Endpoints"
    inputs = [b'endpoint="/reports"']
    expected_out: Any = {"endpoint": ("/reports", {})}
    expected_notes: NoteClassListType = [ENDPOINT_NOT_SECURE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.base_uri = "http://example.com/"
