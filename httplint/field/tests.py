from typing import Any, List, Tuple, Type
import unittest

from httplint.note import Note
from httplint.message import HttpResponseLinter, HttpMessageLinter, HttpRequestLinter


class FakeResponseLinter(HttpResponseLinter):
    """
    A fake response linter for testing.
    """

    def __init__(self) -> None:
        HttpResponseLinter.__init__(self)
        self.base_uri = "http://example.com/foo/bar"
        self.status_phrase = ""


class FakeRequestLinter(HttpRequestLinter):
    """
    A fake request linter for testing.
    """

    def __init__(self) -> None:
        HttpRequestLinter.__init__(self)
        self.base_uri = "http://example.com/foo/bar"
        self.method = "GET"


class FakeHeaders:
    def __init__(self) -> None:
        self.text: List[Tuple[str, str]] = []


class FakeRequest:
    def __init__(self) -> None:
        self.headers = FakeHeaders()
        self.method = "GET"


class FieldTest(unittest.TestCase):
    """
    Testing machinery for headers.
    """

    name: str = ""
    inputs: List[bytes] = []
    expected_out: Any = []
    expected_notes: List[Type[Note]] = []
    message: HttpMessageLinter

    linter_class: Type[HttpMessageLinter] = FakeResponseLinter

    def setUp(self) -> None:
        "Test setup."
        if self.name:
            # pylint: disable=protected-access
            handler = self.linter_class().headers._finder.find_handler(self.name)
            if handler.valid_in_requests and not handler.valid_in_responses:
                self.linter_class = FakeRequestLinter
        self.message = self.linter_class()
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

    def assert_note(
        self, input_bytes: bytes, note: Type[Note], expected_out: Any = None
    ) -> None:
        self.inputs = [input_bytes]
        self.expected_notes = [note]
        self.expected_out = expected_out
        self.setUp()
        self.test_header()
