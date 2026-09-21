import re
from typing import Generic

import http_sf

from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, TMessage
from httplint.util import markdown_context

RE_FLAGS = re.VERBOSE | re.IGNORECASE
CONTEXT_CHARS = 35


class StructuredField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that uses the Structured Fields encoding.
    See: RFC 8941
    """

    nonstandard_syntax = True
    sf_type: str = "item"  # item, list, dict

    def __init__(self, wire_name: str, message: TMessage) -> None:
        super().__init__(wire_name, message)
        self._sf_parsed = False

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.value.append(field_value)
        self._sf_parsed = False

    def finish(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        if getattr(self, "_sf_parsed", False):
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
            problem = str(why)
            context: str = ""
            if hasattr(why, "position") and why.position is not None:
                context = markdown_context(combined_value, why.position, CONTEXT_CHARS)
            add_note(
                STRUCTURED_FIELD_PARSE_ERROR,
                problem=problem,
                context=context,
                category=self.category,
            )
            self.value = None
        except ValueError as why:
            add_note(
                STRUCTURED_FIELD_PARSE_ERROR,
                problem=str(why),
                context="",
                category=self.category,
            )
            self.value = None
        except Exception as why:  # pylint: disable=broad-except
            add_note(
                STRUCTURED_FIELD_PARSE_ERROR,
                problem=str(why),
                context="",
                category=self.category,
            )
            self.value = None

        self._sf_parsed = True
        super().finish(add_note)


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

The parser reports this error: `%(problem)s`

%(context)s"""
