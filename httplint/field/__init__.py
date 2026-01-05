from functools import partial
import re
from typing import (
    Any,
    List,
    Dict,
    Union,
    TYPE_CHECKING,
)
import unittest


from httplint.syntax import rfc9110
from httplint.types import (
    StrFieldListType,
    RawFieldListType,
    FieldDictType,
    AddNoteMethodType,
)

from httplint.field.utils import RE_FLAGS, split_list_field
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
    valid_in_requests: bool
    valid_in_responses: bool
    deprecated: bool = False
    no_coverage: bool = False  # Turns off coverage checks.

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

    def post_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> None:
        """
        Called after the message is complete and other processing has occurred.
        """

    def handle_input(
        self, field_value: str, add_note: AddNoteMethodType, offset: int
    ) -> None:
        """
        Basic input processing on a new field value.
        """

        values = split_list_field(field_value)
        i = 0
        for value in values:
            offset_add_note = partial(
                self.message.notes.add,
                f"offset-{offset}",
                field_name=self.canonical_name,
            )
            i += 1
            if self.syntax:
                element_syntax = (
                    self.syntax.element
                    if isinstance(self.syntax, rfc9110.list_rule)
                    else self.syntax
                )
                if not re.match(rf"^\s*(?:{element_syntax})\s*$", value, RE_FLAGS):
                    offset_add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                parsed_value = self.parse(value.strip(), offset_add_note)
            except ValueError:
                continue
            self.value.append(parsed_value)

    def pre_check(
        self, message: "HttpMessageLinter", add_note: AddNoteMethodType
    ) -> bool:
        """
        Called before parsing or evaluating the field.
        If False is returned, processing is aborted.
        """
        # check whether we're in the right message type
        if self.message.message_type == "request":
            if not self.valid_in_requests:
                add_note(RESPONSE_HDR_IN_REQUEST)
                self.value = None
                return False
        else:
            if not self.valid_in_responses:
                add_note(REQUEST_HDR_IN_RESPONSE)
                self.value = None
                return False

        # check field name syntax
        if not re.match(f"^{rfc9110.token}$", self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)
            return False

        if self.deprecated:
            deprecation_ref = getattr(self, "deprecation_ref", self.reference)
            add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref)

        return True

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        """
        Called when all field lines in the section are available.
        """

        if self.value is not None:
            self.evaluate(add_note)
