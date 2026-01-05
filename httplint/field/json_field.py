import json
import re
from typing import TYPE_CHECKING

from httplint.field import HttpField
from httplint.field.notes import (
    RESPONSE_HDR_IN_REQUEST,
    REQUEST_HDR_IN_RESPONSE,
    FIELD_NAME_BAD_SYNTAX,
    FIELD_DEPRECATED,
)
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter

RE_FLAGS = re.VERBOSE | re.IGNORECASE


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
        # check whether we're in the right message type
        if self.message.message_type == "request":
            if not self.valid_in_requests:
                add_note(RESPONSE_HDR_IN_REQUEST)
                self.value = None
                return
        else:
            if not self.valid_in_responses:
                add_note(REQUEST_HDR_IN_RESPONSE)
                self.value = None
                return

        # check field name syntax
        if not re.match(f"^{rfc9110.token}$", self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)

        if self.deprecated:
            deprecation_ref = getattr(self, "deprecation_ref", self.reference)
            add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref)

        if not self.value:
            self.value = None
            return

        combined_value = f"[{', '.join(self.value)}]"
        try:
            self.value = json.loads(combined_value)
        except json.JSONDecodeError as why:
            add_note(BAD_JSON, error=str(why))
            self.value = None
            return

        self.evaluate(add_note)


class BAD_JSON(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header value isn't valid JSON."
    _text = """\
Each `%(field_name)s` field line must be valid JSON.

The JSON parsing error was:
    %(error)s"""
