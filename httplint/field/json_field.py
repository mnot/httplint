import json
from typing import TYPE_CHECKING

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class JsonField(HttpField):
    """
    A HTTP field that uses the JSON encoding for field values.
    See: https://reschke.github.io/json-fields/
    """

    list_header = False
    nonstandard_syntax = True
    syntax = False
    structured_field = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType) -> None:
        self.value.append(field_value)

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        if self.value:
            combined_value = f"[{', '.join(self.value)}]"
            try:
                self.value = json.loads(combined_value)
            except json.JSONDecodeError as why:
                add_note(BAD_JSON, error=str(why))
                self.value = None

        super().finish(message, add_note)


class BAD_JSON(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header value isn't valid JSON."
    _text = """\
Each `%(field_name)s` field line must be valid JSON.

The JSON parsing error was:
    %(error)s"""
