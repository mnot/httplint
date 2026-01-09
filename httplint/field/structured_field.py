import re
from typing import TYPE_CHECKING

import http_sf

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter

RE_FLAGS = re.VERBOSE | re.IGNORECASE


class StructuredField(HttpField):
    """
    A HTTP field that uses the Structured Fields encoding.
    See: RFC 8941
    """

    nonstandard_syntax = True
    sf_type: str = "item"  # item, list, dict

    def handle_input(
        self, field_value: str, add_note: AddNoteMethodType, offset: int
    ) -> None:
        self.value.append(field_value)

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        combined_value = ", ".join(self.value).strip()

        def on_duplicate_key(key: str, context: str) -> None:
            add_note(DUPLICATE_KEY, key=key, context=context)

        try:
            self.value = http_sf.parse(
                combined_value.encode("utf-8"),
                tltype=self.sf_type,
                on_duplicate_key=on_duplicate_key,
            )
        except http_sf.StructuredFieldError as why:
            problem = f"{why}"
            if hasattr(why, "position") and why.position is not None:
                bad_char_index = why.position
                context_start = max(0, bad_char_index - 20)
                context_end = min(len(combined_value), bad_char_index + 20)
                context = combined_value[context_start:context_end]
                pointer = " " * (bad_char_index - context_start) + "^"
                problem += f"\n\n    {context}\n    {pointer}"
            add_note(STRUCTURED_FIELD_PARSE_ERROR, error=problem)
            self.value = None
        except ValueError as why:
            add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
            self.value = None
        except Exception as why:  # pylint: disable=broad-except
            add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
            self.value = None

        super().finish(message, add_note)


class DUPLICATE_KEY(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "In %(field_name)s, the %(context)s key '%(key)s' is duplicated."
    _text = """\
The %(context)s key '%(key)s' is duplicated. All instances after the first will be ignored."""


class STRUCTURED_FIELD_PARSE_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s field value isn't a valid Structured Field."
    _text = """\
The %(field_name)s field is defined as a
[Structured Field](https://www.rfc-editor.org/rfc/rfc9651.html),
but its value can't be parsed as one. As a result, this field is likely
to be ignored.

The parser reports this error:

%(error)s"""
