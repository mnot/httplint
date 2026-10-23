from functools import partial
from typing import Any, Generic, List, Tuple

from httplint.field import HttpField
from httplint.types import AddNoteMethodType, TMessage


class BrokenField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that allows multiple values, but is not a comma-separated list.
    """

    def __init__(self, wire_name: str, message: TMessage) -> None:
        super().__init__(wire_name, message)
        self.raw_values: List[Tuple[str, int]] = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string value representing a field line, parse and return the result."""
        return field_value

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.raw_values.append((field_value, offset))

    def finish(self, add_note: AddNoteMethodType) -> None:
        parsed_values = []
        for raw_value, offset in self.raw_values:
            # override add_note's subject to be offset-based
            offset_add_note = partial(
                self.message.notes.add,
                f"offset-{offset}",
                field_name=self.canonical_name,
            )
            try:
                with self._syntax_checked(raw_value, offset_add_note):
                    parsed_values.append(self.parse(raw_value.strip(), offset_add_note))
            except ValueError:
                pass
        self.value = parsed_values

        if self.value is not None:
            self.evaluate(add_note)
