from typing import Any, List, Tuple, Type, Iterable
from functools import partial
import unittest

from httplint.i18n import L_
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
        if self.name.lower() in self.message.headers.handlers:
            handler = self.message.headers.handlers[self.name.lower()]
            field_add_note = partial(
                self.message.notes.add,
                f"field-{handler.canonical_name.lower()}",
                field_name=handler.canonical_name,
                field_type=L_("header"),
            )
            handler.post_check(self.message, field_add_note)

        out = self.message.headers.parsed.get(self.name.lower(), "HEADER HANDLER NOT FOUND")
        self.assertEqual(self.expected_out, out)
        all_notes: List[Note] = []

        def collect_notes(notes: Iterable[Note]) -> None:
            for note in notes:
                all_notes.append(note)
                collect_notes(note.subnotes)

        collect_notes(self.message.notes)

        actual_notes = {n.__class__ for n in all_notes}
        expected_notes_set = set(self.expected_notes)

        missing_expected = {
            n.__name__
            for n in expected_notes_set
            if not any(issubclass(a, n) for a in actual_notes)
        }

        unexpected_actual = {
            n.__name__
            for n in actual_notes
            if not any(issubclass(n, e) for e in expected_notes_set)
        }

        diff = missing_expected | unexpected_actual
        for message in all_notes:  # check formatting
            message.vars.update({"field_name": self.name, "response": "response"})
            self.assertTrue(message.detail)
            self.assertTrue(message.summary)
        self.assertEqual(len(diff), 0, f"Mismatched notes: {diff}")
        return None

    def set_context(self, message: "HttpMessageLinter") -> None:
        pass

    def assert_note(self, input_bytes: bytes, note: Type[Note], expected_out: Any = None) -> None:
        self.inputs = [input_bytes]
        self.expected_notes = [note]
        self.expected_out = expected_out
        self.setUp()
        self.test_header()
