from functools import partial
from typing import Dict, TYPE_CHECKING

from httplint.field import HttpField
from httplint.field.finder import HttpFieldFinder
from httplint.note import Note, categories, levels
from httplint.types import StrFieldListType, RawFieldListType, FieldDictType
from httplint.util import f_num

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class FieldSection:
    """
    A field section (headers or trailers).
    """

    max_field_size = 8 * 1024

    def __init__(self, message: "HttpMessageLinter") -> None:
        self.message = message
        self.text: StrFieldListType = (
            []
        )  # unicode version of the field tuples as received
        self.parsed: FieldDictType = {}  # dictionary of parsed field values
        self.size: int = 0  # size of textual header block w/o delimiters, in bytes
        self.handlers: Dict[str, HttpField] = {}
        self._finder = HttpFieldFinder(message, self)

    def process(self, raw_fields: RawFieldListType) -> None:
        """
        Given a list of (bytes name, bytes value) fields and:
            - populate text and parsed
            - calculate the total section size
            - call msg.add_note as appropriate
        """
        offset = 0  # what number header we're on

        for name, value in raw_fields:
            offset += 1
            add_note = partial(self.message.notes.add, f"offset-{offset}")

            # track size
            field_size = len(name) + len(value)
            self.size += field_size

            # decode the field to make it unicode clean
            try:
                str_name = name.decode("ascii", "strict")
            except UnicodeError:
                str_name = name.decode("ascii", "ignore")
                add_note(FIELD_NAME_ENCODING, field_name=str_name)
            try:
                str_value = value.decode("ascii", "strict")
            except UnicodeError:
                str_value = value.decode("iso-8859-1", "replace")
                add_note(FIELD_VALUE_ENCODING, field_name=str_name)
            self.text.append((str_name, str_value))

            handler = self._finder.find_handler(str_name)
            field_add_note = partial(
                add_note,
                field_name=handler.canonical_name,
            )
            handler.handle_input(str_value, field_add_note)

            if field_size > self.max_field_size:
                add_note(
                    FIELD_TOO_LARGE,
                    field_name=handler.canonical_name,
                    field_size=f_num(field_size),
                )

        # check each of the complete header values and get the parsed value
        for _, handler in list(self.handlers.items()):
            field_add_note = partial(
                self.message.notes.add,
                f"field-{handler.canonical_name.lower()}",
                field_name=handler.canonical_name,
            )
            handler.finish(self.message, field_add_note)
            self.parsed[handler.norm_name] = handler.value


class FIELD_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header is very large (%(field_size)s bytes)."
    _text = """\
Some implementations limit the size of any single header line."""


class FIELD_NAME_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header's name contains non-ASCII characters."
    _text = """\
HTTP field names can only contain ASCII characters."""


class FIELD_VALUE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header's value contains non-ASCII characters."
    _text = """\
HTTP fields notionally use the ISO-8859-1 character set, but in most cases are pure ASCII
(a subset of this encoding).

This header has non-ASCII characters, which have been interpreted as being encoded in
ISO-8859-1. If another encoding is used (e.g., UTF-8), the results may be unpredictable."""
