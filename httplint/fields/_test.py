from typing import Any, List, Type, Union, TYPE_CHECKING
import unittest

from httplint.field_section import FieldSection
from httplint.note import Note
from httplint.message import HttpResponse
from httplint.type import (
    AddNoteMethodType,
)

if TYPE_CHECKING:
    from httplint.fields import HttpMessage


class TestMessage(HttpResponse):
    """
    A dummy HTTP message, for testing.
    """

    def __init__(self, add_note: AddNoteMethodType = None) -> None:
        HttpResponse.__init__(self)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.status_phrase = ""
        self.note_list: List[Note] = []
        self.note_classes: List[str] = []

    def dummy_add_note(
        self, subject: str, note: Type[Note], **kw: Union[str, int]
    ) -> None:
        "Record the classes of notes set."
        self.note_list.append(note(subject, **kw))
        self.note_classes.append(note.__name__)


class FieldTest(unittest.TestCase):
    """
    Testing machinery for headers.
    """

    name: str = None
    inputs: List[bytes] = []
    expected_out: Any = []
    expected_notes: List[Type[Note]] = []

    def setUp(self) -> None:
        "Test setup."
        self.message = TestMessage()
        self.set_context(self.message)

    def test_header(self) -> Any:
        "Test the header."
        if not self.name:
            return self.skipTest("")
        name = self.name.encode("utf-8")
        section = FieldSection()
        section.process([(name, inp) for inp in self.inputs], self.message)
        out = section.parsed.get(self.name.lower(), "HEADER HANDLER NOT FOUND")
        self.assertEqual(self.expected_out, out)
        diff = {n.__name__ for n in self.expected_notes}.symmetric_difference(
            set(self.message.note_classes)
        )
        for message in self.message.note_list:  # check formatting
            message.vars.update({"field_name": self.name, "response": "response"})
            self.assertTrue(message.text % message.vars)
            self.assertTrue(message.summary % message.vars)
        self.assertEqual(len(diff), 0, f"Mismatched notes: {diff}")
        return None

    def set_context(self, message: "HttpMessage") -> None:
        pass
