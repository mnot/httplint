from copy import copy
from functools import partial
import re
import sys
from typing import (
    Any,
    Callable,
    List,
    Dict,
    Optional,
    Tuple,
    Type,
    Union,
    TYPE_CHECKING,
)
import unittest

from ..request import HttpRequest
from ..response import HttpResponse
from ..syntax import rfc7230, rfc7231
from ..type import (
    StrFieldListType,
    RawFieldListType,
    FieldDictType,
    AddNoteMethodType,
)
from ..util import f_num

from ._utils import RE_FLAGS, parse_date, split_string
from ._notes import *
from ._test import FieldTest

if TYPE_CHECKING:
    from ..message import (
        HttpMessage,
    )  # pylint: disable=cyclic-import

# base URLs for references
RFC2616 = "http://tools.ietf.org/html/rfc2616.html#%s"
RFC6265 = "http://tools.ietf.org/html/rfc6265.html#%s"
RFC6266 = "http://tools.ietf.org/html/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000


class HttpField:
    """A HTTP Field."""

    canonical_name: str = None
    description: str = None
    reference: str = None
    syntax: Union[
        str, rfc7230.list_rule, bool
    ] = None  # Verbose regular expression to match.
    list_header: bool = None  # Can be split into values on commas.
    nonstandard_syntax: bool = False  # Don't check for a single value at the end.
    deprecated: bool = None
    valid_in_requests: bool = None
    valid_in_responses: bool = None
    no_coverage: bool = False  # Turns off coverage checks.

    def __init__(self, wire_name: str, message: "HttpMessage") -> None:
        self.wire_name = wire_name.strip()
        self.message = message
        self.norm_name = self.wire_name.lower()
        if self.canonical_name is None:
            self.canonical_name = self.wire_name
        self.value: Any = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string value and an add_note function, parse and return the result."""
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        """
        Called once processing is done; typically used to evaluate an entire
        field's values.
        """

    def handle_input(self, field_value: str, add_note: AddNoteMethodType) -> None:
        """
        Basic input processing on a new field value.
        """

        # split before processing if a list field
        if self.list_header:
            values = self.split_list_field(field_value)
        else:
            values = [field_value]
        for value in values:
            # check field value syntax
            if self.syntax:
                element_syntax = (
                    self.syntax.element
                    if isinstance(self.syntax, rfc7230.list_rule)
                    else self.syntax
                )
                if not re.match(rf"^\s*(?:{element_syntax})\s*$", value, RE_FLAGS):
                    add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                parsed_value = self.parse(value.strip(), add_note)
            except ValueError:
                continue  # we assume that the parser made a note of the problem.
            self.value.append(parsed_value)

    @staticmethod
    def split_list_field(field_value: str) -> List[str]:
        "Split a field field value on commas. needs to conform to the #rule."
        return [
            f.strip()
            for f in re.findall(
                r'((?:[^",]|%s)+)(?=%s|\s*$)'
                % (rfc7230.quoted_string, r"(?:\s*(?:,\s*)+)"),
                field_value,
                RE_FLAGS,
            )
            if f
        ] or []

    def finish(self, message: "HttpMessage", add_note: AddNoteMethodType) -> None:
        """
        Called when all field lines in the section are available.
        """

        # check field name syntax
        if not re.match(f"^{rfc7230.token}$", self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)
        if self.deprecated:
            deprecation_ref = getattr(self, "deprecation_ref", self.reference)
            add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref)
        if not self.list_header and not self.nonstandard_syntax:
            if not self.value:
                self.value = None
            elif len(self.value) == 1:
                self.value = self.value[-1]
            elif len(self.value) > 1:
                add_note(SINGLE_HEADER_REPEAT)
                self.value = self.value[-1]
        if isinstance(message, HttpRequest):
            if not self.valid_in_requests:
                add_note(RESPONSE_HDR_IN_REQUEST)
        else:
            if not self.valid_in_responses:
                add_note(REQUEST_HDR_IN_RESPONSE)
        self.evaluate(add_note)
