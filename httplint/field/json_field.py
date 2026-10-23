import json
from typing import Any, Generic

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, TMessage

MAX_JSON_DEPTH = 100


def _too_deep(value: Any) -> bool:
    """
    Iteratively check nesting, so the answer doesn't depend on the recursion limit.
    The outer list that finish() wraps around the field lines doesn't count.
    """
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (list, dict)):
            if depth > MAX_JSON_DEPTH:
                return True
            children = item.values() if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)
    return False


class JsonField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that uses the JSON encoding for field values.
    See: https://reschke.github.io/json-fields/
    """

    nonstandard_syntax = True
    syntax = False

    def __init__(self, wire_name: str, message: TMessage) -> None:
        super().__init__(wire_name, message)
        self._json_parsed = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.value.append(field_value)
        self._json_parsed = False

    def finish(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        # A further process() call re-finishes every handler; the value is parsed by then.
        if self._json_parsed:
            return

        combined_value = f"[{', '.join(self.value)}]"
        try:
            self.value = json.loads(combined_value)
        except json.JSONDecodeError as why:
            add_note(BAD_JSON, error=str(why), category=self.category)
            self.value = None
        except RecursionError:
            add_note(BAD_JSON, error="nested too deeply", category=self.category)
            self.value = None
        except ValueError as why:
            # Beyond JSONDecodeError, the only ValueError is Python's int-digit limit.
            error = "number too large" if "digits" in str(why) else "value out of range"
            add_note(BAD_JSON, error=error, category=self.category)
            self.value = None
        else:
            if _too_deep(self.value):
                add_note(BAD_JSON, error="nested too deeply", category=self.category)
                self.value = None

        self._json_parsed = True
        super().finish(add_note)


class BAD_JSON(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header value isn't valid JSON."
    _text = """\
Each `%(field_name)s` field line must be valid JSON.

The JSON parsing error was:
    %(error)s"""
