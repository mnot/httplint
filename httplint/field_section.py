from functools import partial
import importlib
import sys
from typing import (
    Any,
    Dict,
    Optional,
    Type,
    TYPE_CHECKING,
)

from httplint.fields import HttpField
from httplint.note import Note, categories, levels
from httplint.types import (
    StrFieldListType,
    RawFieldListType,
    FieldDictType,
    AddNoteMethodType,
)
from httplint.util import f_num

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class FieldSection:
    """
    A field section (headers or trailers).
    """

    # map of field name aliases, lowercase-normalised
    field_aliases = {
        "x-pad-for-netscrape-bug": "x-pad",
        "xx-pad": "x-pad",
        "x-browseralignment": "x-pad",
        "nncoection": "connectiox",
        "cneonction": "connectiox",
        "yyyyyyyyyy": "connectiox",
        "xxxxxxxxxx": "connectiox",
        "x_cnection": "connectiox",
        "_onnection": "connectiox",
    }

    max_field_size = 8 * 1024

    def __init__(self) -> None:
        self.text: StrFieldListType = []  # unicode version of the field tuples
        self.parsed: FieldDictType = {}  # dictionary of parsed field values
        self.size: int = 0
        self._handlers: Dict[str, HttpField] = {}

    def process(
        self, raw_fields: RawFieldListType, message: "HttpMessageLinter"
    ) -> None:
        """
        Given a list of (bytes name, bytes value) fields and:
         - populate text and parsed
         - calculate the total section size
         - call msg.add_note as appropriate
        """
        offset = 0  # what number header we're on

        for name, value in raw_fields:
            offset += 1
            add_note = partial(message.notes.add, f"offset-{offset}")

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

            handler = self.get_handler(str_name, message)
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
        for _, handler in list(self._handlers.items()):
            field_add_note = partial(
                message.notes.add,
                f"field-{handler.canonical_name.lower()}",
                field_name=handler.canonical_name,
            )
            handler.finish(message, field_add_note)
            self.parsed[handler.norm_name] = handler.value

    def get_handler(self, field_name: str, message: "HttpMessageLinter") -> HttpField:
        """
        If a handler has already been instantiated for field_name, return it;
        otherwise, instantiate and return a new one.
        """
        norm_name = field_name.lower()
        if norm_name in self._handlers:
            return self._handlers[norm_name]
        handler = self.find_handler(field_name)(field_name, message)
        self._handlers[norm_name] = handler
        return handler

    @staticmethod
    def find_handler(
        field_name: str, default: bool = True
    ) -> Optional[Type[HttpField]]:
        """
        Return a handler class for the given field name.

        If default is true, return a dummy if one isn't found; otherwise, None.
        """

        name_token = FieldSection.name_token(field_name)
        module = FieldSection.find_field_module(name_token)
        if module and hasattr(module, name_token):
            return getattr(module, name_token)  # type: ignore
        if default:
            return UnknownHttpField
        return None

    @staticmethod
    def find_field_module(field_name: str) -> Any:
        """
        Return a module for the given field name, or None if it can't be found.
        """
        name_token = FieldSection.name_token(field_name)
        if name_token[0] == "_":  # these are special
            return None
        if name_token in FieldSection.field_aliases:
            name_token = FieldSection.field_aliases[name_token]
        try:
            module_name = f"httplint.fields.{name_token}"
            importlib.import_module(module_name)
            return sys.modules[module_name]
        except (ImportError, KeyError, TypeError):
            return None

    @staticmethod
    def name_token(field_name: str) -> str:
        """
        Return a tokenised, python-friendly name for a field.
        """
        return field_name.replace("-", "_").lower()


class UnknownHttpField(HttpField):
    """A HTTP field that we don't recognise."""

    list_header = True
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        return


class FIELD_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(field_name)s header is very large (%(header_size)s bytes)."
    text = """\
Some implementations limit the size of any single header line."""


class FIELD_NAME_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The %(field_name)s header's name contains non-ASCII characters."
    text = """\
HTTP field names can only contain ASCII characters."""


class FIELD_VALUE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(field_name)s header's value contains non-ASCII characters."
    text = """\
HTTP fields notionally use the ISO-8859-1 character set, but in most cases are pure ASCII
(a subset of this encoding).

This header has non-ASCII characters, which have been interpreted as being encoded in
ISO-8859-1. If another encoding is used (e.g., UTF-8), the results may be unpredictable."""
