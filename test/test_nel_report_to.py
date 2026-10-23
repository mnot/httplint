"""
NEL's report_to resolves against Report-To groups as well as Reporting-Endpoints.
"""

import unittest
from typing import Any, List, Tuple

from httplint.field.parsers.nel import (
    NEL_CONFIGURED,
    NEL_REPORT_TO_GROUP_UNUSABLE,
    NEL_REPORT_TO_MISSING,
)
from httplint.message import HttpResponseLinter

NEL = (b"NEL", b'{"report_to": "g", "max_age": 1}')
REPORT_TO = b'{"group": "%s", "max_age": 10, "endpoints": [{"url": "https://example.com/r"}]}'
INSECURE_REPORT_TO = b'{"group": "g", "max_age": 10, "endpoints": [{"url": "http://example.com/r"}]}'
NO_ENDPOINTS_REPORT_TO = b'{"group": "g", "max_age": 10}'


def note_classes(headers: List[Tuple[bytes, bytes]]) -> List[Any]:
    response = HttpResponseLinter()
    response.base_uri = "https://example.com/"
    response.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    response.process_headers(headers)
    response.finish_content(True)
    return [type(note) for note in response.notes]


class NelReportToTest(unittest.TestCase):
    def test_report_to_group(self) -> None:
        classes = note_classes([NEL, (b"Report-To", REPORT_TO % b"g")])
        self.assertIn(NEL_CONFIGURED, classes)
        self.assertNotIn(NEL_REPORT_TO_MISSING, classes)

    def test_report_to_group_across_lines(self) -> None:
        classes = note_classes(
            [NEL, (b"Report-To", REPORT_TO % b"other"), (b"Report-To", REPORT_TO % b"g")]
        )
        self.assertIn(NEL_CONFIGURED, classes)
        self.assertNotIn(NEL_REPORT_TO_MISSING, classes)

    def test_other_group(self) -> None:
        classes = note_classes([NEL, (b"Report-To", REPORT_TO % b"other")])
        self.assertIn(NEL_REPORT_TO_MISSING, classes)
        self.assertNotIn(NEL_CONFIGURED, classes)

    def test_insecure_group(self) -> None:
        classes = note_classes([NEL, (b"Report-To", INSECURE_REPORT_TO)])
        self.assertIn(NEL_REPORT_TO_GROUP_UNUSABLE, classes)
        self.assertNotIn(NEL_REPORT_TO_MISSING, classes)
        self.assertNotIn(NEL_CONFIGURED, classes)

    def test_group_without_endpoints(self) -> None:
        classes = note_classes([NEL, (b"Report-To", NO_ENDPOINTS_REPORT_TO)])
        self.assertIn(NEL_REPORT_TO_GROUP_UNUSABLE, classes)
        self.assertNotIn(NEL_REPORT_TO_MISSING, classes)
        self.assertNotIn(NEL_CONFIGURED, classes)

    def test_reporting_endpoints_beat_unusable_group(self) -> None:
        classes = note_classes(
            [
                NEL,
                (b"Report-To", INSECURE_REPORT_TO),
                (b"Reporting-Endpoints", b'g="https://example.com/r"'),
            ]
        )
        self.assertIn(NEL_CONFIGURED, classes)
        self.assertNotIn(NEL_REPORT_TO_GROUP_UNUSABLE, classes)

    def test_reporting_endpoints(self) -> None:
        classes = note_classes([NEL, (b"Reporting-Endpoints", b'g="https://example.com/r"')])
        self.assertIn(NEL_CONFIGURED, classes)
        self.assertNotIn(NEL_REPORT_TO_MISSING, classes)

    def test_neither(self) -> None:
        classes = note_classes([NEL])
        self.assertIn(NEL_REPORT_TO_MISSING, classes)
        self.assertNotIn(NEL_CONFIGURED, classes)


class JsonFieldRepeatedProcessTest(unittest.TestCase):
    "A second process_headers() call re-finishes every handler, including JSON fields."

    def test_second_call(self) -> None:
        response = HttpResponseLinter()
        response.base_uri = "https://example.com/"
        response.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        response.process_headers([NEL, (b"Report-To", REPORT_TO % b"g")])
        response.process_headers([(b"Server", b"x")])
        self.assertEqual(response.headers.parsed["nel"], [{"report_to": "g", "max_age": 1}])
        self.assertEqual(len(response.headers.parsed["report-to"]), 1)


if __name__ == "__main__":
    unittest.main()
