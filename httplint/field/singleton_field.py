import re
from typing import TYPE_CHECKING, List, Any

from httplint.field import HttpField
from httplint.field.utils import RE_FLAGS
from httplint.field import BAD_SYNTAX
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class SingletonField(HttpField):
    """
    A HTTP field that strictly allows only one value.
    """

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        super().__init__(wire_name, message)
        self.raw_values: List[str] = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string representing a field line, parse and return the result."""
        return field_value

    def handle_input(self, field_value: str, add_note: "AddNoteMethodType", offset: int) -> None:
        self.raw_values.append(field_value)

    def finish(self, message: "HttpMessageLinter", add_note: "AddNoteMethodType") -> None:
        if not self.raw_values:
            self.value = None
        else:
            if len(self.raw_values) > 1:
                add_note(SINGLE_HEADER_REPEAT)
            first_raw = self.raw_values[0]
            if self.syntax:
                if not re.match(rf"^\s*(?:{self.syntax})\s*$", first_raw, RE_FLAGS):
                    if self.report_syntax:
                        add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                self.value = self.parse(first_raw.strip(), add_note)
            except ValueError:
                self.value = None

        if self.value is not None:
            self.evaluate(add_note)


class SINGLE_HEADER_REPEAT(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Only one %(field_name)s field is allowed in a message."
    _text = """\
This field is designed to only occur once in a message. When it occurs more than once, a receiver
needs to choose the one to use, which can lead to interoperability problems, since different
implementations may make different choices."""
