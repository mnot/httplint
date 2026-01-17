from abc import ABC, abstractmethod
import re
from typing import (
    Any,
    List,
    Dict,
    Union,
    TYPE_CHECKING,
)


from httplint.syntax import rfc9110
from httplint.types import (
    StrFieldListType,
    RawFieldListType,
    FieldDictType,
    AddNoteMethodType,
)

from httplint.field.utils import RE_FLAGS
from httplint.note import Note, categories, levels


if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter

# base URLs for references
RFC2616 = "https://www.rfc-editor.org/rfc/rfc2616.html#%s"
RFC6265 = "https://www.rfc-editor.org/rfc/rfc6265.html#%s"
RFC6266 = "https://www.rfc-editor.org/rfc/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000


class HttpField(ABC):
    """A HTTP Field."""

    canonical_name: str
    description: str
    reference: str
    category: categories = categories.GENERAL
    syntax: Union[
        str, rfc9110.list_rule, bool
    ]  # Verbose regular expression to match, or False to indicate no syntax.
    report_syntax: bool = True  # If False, syntax mismatch suppresses BAD_SYNTAX.
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

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        """
        Called once processing is done; typically used to evaluate an entire
        field's values.
        """

    def post_check(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        """
        Called after the message is complete and other processing has occurred.
        """

    @abstractmethod
    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        """
        Basic input processing on a new field value.
        """

    def pre_check(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> bool:
        """
        Called before parsing or evaluating the field.
        If False is returned, processing is aborted.
        """
        # check whether we're in the right message type
        if self.message.message_type == "request":
            if not self.valid_in_requests:
                add_note(RESPONSE_HDR_IN_REQUEST, category=self.category)
                self.value = None
                return False
        else:
            if not self.valid_in_responses:
                add_note(REQUEST_HDR_IN_RESPONSE, category=self.category)
                self.value = None
                return False

        # check field name syntax
        if not re.match(f"^{rfc9110.token}$", self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)
            return False

        if self.deprecated:
            deprecation_ref = getattr(self, "deprecation_ref", self.reference)
            add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref, category=self.category)

        return True

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        """
        Called when all field lines in the section are available.
        """

        if self.value is not None:
            self.evaluate(add_note)


class FIELD_NAME_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" is not a valid field name.'
    _text = """\
Field names are limited to the `token` production in HTTP; i.e., they can't contain parenthesis,
angle brackets (<>), ampersands (@), commas, semicolons, colons, backslashes (\\), forward
slashes (/), quotes, square brackets ([]), question marks, equals signs (=), curly brackets ({})
spaces or tabs."""


# BAD_SYNTAX should NOT be used by specific Notes.
class BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s field value doesn't conform to its specified syntax."
    _text = """\
The value for this field has syntax specified using 
[Augmented BNF](https://www.rfc-editor.org/rfc/rfc5234.html),
but doesn't conform to it. See [the field's ABNF](%(ref_uri)s) for more information.

This error may or may not prevent recipients from parsing the field; fixing it will
improve interoperability.
"""


# BAD_SYNTAX_DETAILED should NOT be used by specific Notes.
class BAD_SYNTAX_DETAILED(BAD_SYNTAX):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s field value doesn't conform to its specified syntax."
    _text = """\
The value for this field has syntax specified using 
[Augmented BNF](https://www.rfc-editor.org/rfc/rfc5234.html),
but doesn't conform to it. See [the field's ABNF](%(ref_uri)s) for more information.

This error may or may not prevent recipients from parsing the field; fixing it will
improve interoperability.

%(problem)s"""


class REQUEST_HDR_IN_RESPONSE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" isn\'t valid in a response.'
    _text = """\
The %(field_name)s field only has meaning in requests. Sending it a response
doesn't do anything. REDbot (and most recipients) will ignore it."""


class RESPONSE_HDR_IN_REQUEST(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" isn\'t valid in a request.'
    _text = """\
The %(field_name)s field only has meaning in responses. Sending it in a request
doesn't do anything. REDbot (and most recipients) will ignore it."""


class FIELD_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header is deprecated."
    _text = """\
This field is no longer recommended for use, because of interoperability problems and/or
lack of use. This field should probably be removed.

See [the deprecation notice](%(deprecation_ref)s) for more information."""
