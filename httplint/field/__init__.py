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

import http_sf

# from httplint.message import HttpRequest
from httplint.syntax import rfc9110
from httplint.types import (
    StrFieldListType,
    RawFieldListType,
    FieldDictType,
    AddNoteMethodType,
)
from httplint.util import f_num

from httplint.field.utils import (
    RE_FLAGS,
    parse_http_date,
    split_string,
    split_list_field,
)
from httplint.field.notes import *

if TYPE_CHECKING:
    from httplint.message import (
        HttpMessageLinter,
    )

# base URLs for references
RFC2616 = "https://www.rfc-editor.org/rfc/rfc2616.html#%s"
RFC6265 = "https://www.rfc-editor.org/rfc/rfc6265.html#%s"
RFC6266 = "https://www.rfc-editor.org/rfc/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000


class HttpField:
    """A HTTP Field."""

    canonical_name: str
    description: str
    reference: str
    syntax: Union[
        str, rfc9110.list_rule, bool
    ]  # Verbose regular expression to match, or False to indicate no syntax.
    # If structured_field is True, this is ignored.
    list_header: bool  # Can be split into values on commas.
    valid_in_requests: bool
    valid_in_responses: bool
    nonstandard_syntax: bool = False  # Don't check for a single value at the end.
    deprecated: bool = False
    no_coverage: bool = False  # Turns off coverage checks.
    structured_field: bool = False
    sf_type: str = "item"  # item, list, dict

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        self.wire_name = wire_name.strip()
        self.message = message
        self.norm_name = self.wire_name.lower()
        if not hasattr(self, "canonical_name"):
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

        # handle structured fields separately during finish
        if self.structured_field:
            self.value.append(field_value)
            return

        # split before processing if a list field
        if self.list_header:
            values = split_list_field(field_value)
        else:
            values = [field_value]
        for value in values:
            # check field value syntax
            if self.syntax:
                element_syntax = (
                    self.syntax.element
                    if isinstance(self.syntax, rfc9110.list_rule)
                    else self.syntax
                )
                if not re.match(rf"^\s*(?:{element_syntax})\s*$", value, RE_FLAGS):
                    add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                parsed_value = self.parse(value.strip(), add_note)
            except ValueError:
                continue  # we assume that the parser made a note of the problem.
            self.value.append(parsed_value)

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        """
        Called when all field lines in the section are available.
        """

        # check field name syntax
        if not re.match(f"^{rfc9110.token}$", self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)

        if self.structured_field:
            combined_value = ", ".join(self.value).strip()
            parsed_value: Any = None
            try:
                if self.sf_type == "list":
                    _, parsed_value = http_sf.parse_list(combined_value.encode("utf-8"))
                elif self.sf_type == "dictionary":
                    _, parsed_value = http_sf.parse_dictionary(
                        combined_value.encode("utf-8")
                    )
                elif self.sf_type == "item":
                    _, parsed_value = http_sf.parse_item(combined_value.encode("utf-8"))
                else:
                    raise ValueError(f"Unknown sf_type: {self.sf_type}")
                self.value = parsed_value
            except ValueError as why:
                add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
                self.value = None
            except Exception as why:  # pylint: disable=broad-except
                add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
                self.value = None
        if self.deprecated:
            deprecation_ref = getattr(self, "deprecation_ref", self.reference)
            add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref)
        if (
            not self.list_header
            and not self.nonstandard_syntax
            and not self.structured_field
        ):
            if not self.value:
                self.value = None
            elif len(self.value) == 1:
                self.value = self.value[-1]
            elif len(self.value) > 1:
                add_note(SINGLE_HEADER_REPEAT)
                self.value = self.value[-1]
        #        if isinstance(message, HttpRequest):
        #            if not self.valid_in_requests:
        #                add_note(RESPONSE_HDR_IN_REQUEST)
        #        else:
        #            if not self.valid_in_responses:
        #                add_note(REQUEST_HDR_IN_RESPONSE)
        self.evaluate(add_note)
