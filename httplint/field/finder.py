import importlib
import sys

from typing import (
    Any,
    Optional,
    Type,
    TYPE_CHECKING,
)

from httplint.field import HttpField
from httplint.field import deprecated
from httplint.types import AddNoteMethodType


if TYPE_CHECKING:
    from httplint.field.section import FieldSection
    from httplint.message import HttpMessageLinter


class HttpFieldFinder:
    """Finds the linter for a given HTTP field."""

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

    def __init__(
        self,
        message: "HttpMessageLinter",
        field_section: Optional["FieldSection"] = None,
    ) -> None:
        self.message = message
        self.field_section = field_section

    def find_handler(self, field_name: str) -> HttpField:
        """
        If a handler has already been instantiated for field_name, return it;
        otherwise, instantiate and return a new one.
        """
        norm_name = field_name.lower()
        if self.field_section and norm_name in self.field_section.handlers:
            return self.field_section.handlers[norm_name]
        handler_class = self.find_handler_class(field_name) or UnknownHttpField
        handler = handler_class(field_name, self.message)
        if self.field_section:
            self.field_section.handlers[norm_name] = handler
        return handler

    @staticmethod
    def find_handler_class(field_name: str) -> Optional[Type[HttpField]]:
        """
        Return a handler class for the given field name. Returns None if not found.
        """

        name_token = HttpFieldFinder.name_token(field_name)
        module = HttpFieldFinder.find_module(name_token)
        if module and hasattr(module, name_token):
            return getattr(module, name_token)  # type: ignore
        if field_name.lower() in deprecated.field_lookup:
            return deprecated.DeprecatedField
        return None

    @staticmethod
    def find_module(field_name: str) -> Any:
        """
        Return a module for the given field name, or None if it can't be found.
        """
        name_token = HttpFieldFinder.name_token(field_name)
        if name_token[0:1] == "_":  # these are special
            return None
        if name_token in HttpFieldFinder.field_aliases:
            name_token = HttpFieldFinder.field_aliases[name_token]
        try:
            module_name = f"httplint.field.parsers.{name_token}"
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

    syntax = False
    list_header = True
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        return


def get_field_description(field_name: str) -> Optional[str]:
    """Return the description for the named field, or None if not found."""
    handler_class = HttpFieldFinder.find_handler_class(field_name)
    if handler_class is not None and handler_class.description:
        return handler_class.description
    return None
