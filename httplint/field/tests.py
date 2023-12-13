from typing import Any, List, Type
import unittest

from httplint.note import Note
from httplint.message import HttpResponseLinter, HttpMessageLinter


class FakeMessageLinter(HttpResponseLinter):
    """
    A fake linter, for testing.
    """

    def __init__(self) -> None:
        HttpResponseLinter.__init__(self)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.status_phrase = ""


class FieldTest(unittest.TestCase):
    """
    Testing machinery for headers.
    """

    name: str
    inputs: List[bytes] = []
    expected_out: Any = []
    expected_notes: List[Type[Note]] = []

    def setUp(self) -> None:
        "Test setup."
        self.message = FakeMessageLinter()
        self.set_context(self.message)

    def test_header(self) -> Any:
        "Test the header."
        if not self.name:
            return self.skipTest("no name")
        name = self.name.encode("utf-8")
        self.message.headers.process([(name, val) for val in self.inputs])
        out = self.message.headers.parsed.get(
            self.name.lower(), "HEADER HANDLER NOT FOUND"
        )
        self.assertEqual(self.expected_out, out)
        diff = {n.__name__ for n in self.expected_notes}.symmetric_difference(
            {n.__class__.__name__ for n in self.message.notes}
        )
        for message in self.message.notes:  # check formatting
            message.vars.update({"field_name": self.name, "response": "response"})
            self.assertTrue(message.detail)
            self.assertTrue(message.summary)
        self.assertEqual(len(diff), 0, f"Mismatched notes: {diff}")
        return None

    def set_context(self, message: "HttpMessageLinter") -> None:
        pass
