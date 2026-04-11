import json
from typing import Generic

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, TMessage


class JsonField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that uses the JSON encoding for field values.
    See: https://reschke.github.io/json-fields/
    """

    nonstandard_syntax = True
    syntax = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.value.append(field_value)

    def finish(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        combined_value = f"[{', '.join(self.value)}]"
        try:
            self.value = json.loads(combined_value)
        except json.JSONDecodeError as why:
            add_note(BAD_JSON, error=str(why), category=self.category)
            self.value = None

        super().finish(add_note)


class BAD_JSON(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header value isn't valid JSON."
    _text = """\
Each `%(field_name)s` field line must be valid JSON.

The JSON parsing error was:
    %(error)s"""
