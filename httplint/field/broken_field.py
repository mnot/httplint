import re
from typing import TYPE_CHECKING, List

from httplint.field import HttpField
from httplint.field.utils import RE_FLAGS
from httplint.field.notes import BAD_SYNTAX

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter
    from httplint.types import AddNoteMethodType


class BrokenField(HttpField):
    """
    A HTTP field that allows multiple values, but is not a comma-separated list.
    """

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        super().__init__(wire_name, message)
        self.raw_values: List[str] = []

    def handle_input(self, field_value: str, add_note: "AddNoteMethodType") -> None:
        self.raw_values.append(field_value)

    def finish(
        self, message: "HttpMessageLinter", add_note: "AddNoteMethodType"
    ) -> None:
        parsed_values = []
        for raw_value in self.raw_values:
            if self.syntax:
                if not re.match(rf"^\s*(?:{self.syntax})\s*$", raw_value, RE_FLAGS):
                    add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                parsed_values.append(self.parse(raw_value.strip(), add_note))
            except ValueError:
                pass
        self.value = parsed_values

        if self.value is not None:
            self.evaluate(add_note)
