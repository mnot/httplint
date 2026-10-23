from typing import Any, Generic, List

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, TMessage


class SingletonField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that strictly allows only one value.
    """

    def __init__(self, wire_name: str, message: TMessage) -> None:
        super().__init__(wire_name, message)
        self.raw_values: List[str] = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string representing a field line, parse and return the result.
        Raise ValueError if parsing fails.
        """
        return field_value

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.raw_values.append(field_value)

    def finish(self, add_note: AddNoteMethodType) -> None:
        if not self.raw_values:
            self.value = None
        else:
            if len(self.raw_values) > 1:
                add_note(SINGLE_HEADER_REPEAT)
            first_raw = self.raw_values[0]
            try:
                with self._syntax_checked(first_raw, add_note):
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
