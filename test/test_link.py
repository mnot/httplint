import unittest
from typing import List

from httplint.field.tests import FakeResponseLinter


def link_notes(value: bytes) -> FakeResponseLinter:
    linter = FakeResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(b"Link", value)])
    linter.finish_content(True)
    return linter


def names(linter: FakeResponseLinter) -> List[str]:
    return [n.__class__.__name__ for n in linter.notes]


class MalformedHintTest(unittest.TestCase):
    "Only a link without a syntax defect gets a resource hint note."

    def test_only_malformed_link_loses_hint(self) -> None:
        linter = link_notes(b"<http://example.com/bad; rel=preload, </good.css>; rel=preload")
        self.assertEqual(names(linter).count("BAD_SYNTAX"), 1)
        hints = [n for n in linter.notes if n.__class__.__name__ == "LINK_RESOURCE_HINTS"]
        self.assertEqual(len(hints), 1)
        detail = str(hints[0].detail)
        self.assertIn("/good.css", detail)
        self.assertNotIn("example.com/bad", detail)

    def test_all_malformed_no_hint(self) -> None:
        linter = link_notes(b"<http://example.com/a; rel=preload, /b; rel=preconnect")
        self.assertEqual(names(linter).count("BAD_SYNTAX"), 2)
        self.assertNotIn("LINK_RESOURCE_HINTS", names(linter))

    def test_well_formed_keeps_hint(self) -> None:
        linter = link_notes(b"</a.css>; rel=preload, <https://cdn.example.com>; rel=preconnect")
        self.assertEqual(names(linter).count("LINK_RESOURCE_HINTS"), 1)
        self.assertNotIn("BAD_SYNTAX", names(linter))


if __name__ == "__main__":
    unittest.main()
