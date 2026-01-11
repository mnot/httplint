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

    nonstandard_syntax = True
    syntax = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.value.append(field_value)

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        combined_value = f"[{', '.join(self.value)}]"
        try:
            self.value = json.loads(combined_value)
        except json.JSONDecodeError as why:
            add_note(BAD_JSON, error=str(why), category=self.category)
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
