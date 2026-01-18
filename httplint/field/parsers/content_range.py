from dataclasses import dataclass
from typing import Optional, Tuple

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter, HttpResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


@dataclass
class ContentRangeValue:
    unit: str
    first_byte_pos: Optional[int]
    last_byte_pos: Optional[int]
    complete_length: Optional[int]


class content_range(SingletonField):
    canonical_name = "Content-Range"
    description = """\
The `Content-Range` response header is sent in a `206` (Partial Content) response to indicate
where in the full response content the partial content is located. It is also used
in `416` (Requested Range Not Satisfiable) responses."""
    reference = f"{rfc9110.SPEC_URL}#field.content-range"
    syntax = rfc9110.Content_Range
    report_syntax = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Optional[ContentRangeValue]:
        self._check_status(add_note)

        try:
            unit, rest = field_value.split(" ", 1)
        except ValueError:
            # if we see a slash, it's likely the unit is missing
            if "/" in field_value:
                add_note(CONTENT_RANGE_MISSING_UNIT)
            raise

        try:
            rng, len_str = rest.split("/", 1)
        except ValueError:
            add_note(CONTENT_RANGE_MISSING_SLASH)
            raise

        if rng == "*" and len_str == "*":
            add_note(CONTENT_RANGE_INVALID_ASTERISK)
            raise ValueError

        complete_length = self._parse_length(len_str, add_note)
        if complete_length is None and len_str != "*":
            # length parsing failed; already noted
            raise ValueError

        first_byte_pos, last_byte_pos = self._parse_range_spec(rng, add_note)
        # Check for * failure (None, None returned for generic failure or *)
        # We need to distinguish between "*" (valid for unsatisfiable) and error.

        if rng == "*":
            if isinstance(self.message, HttpResponseLinter) and self.message.status_code == 206:
                add_note(CONTENT_RANGE_UNSATISFIED_BAD_SC)
        elif first_byte_pos is None:
            # Error in range parsing; already noted
            raise ValueError
        else:
            # We have a valid range tuple
            if first_byte_pos is not None and last_byte_pos is not None:
                if first_byte_pos > last_byte_pos:
                    add_note(RANGE_INVALID)
                if complete_length is not None and last_byte_pos >= complete_length:
                    add_note(RANGE_INVALID)

        return ContentRangeValue(unit, first_byte_pos, last_byte_pos, complete_length)

    def _check_status(self, add_note: AddNoteMethodType) -> None:
        if isinstance(self.message, HttpResponseLinter) and self.message.status_code not in [
            206,
            416,
        ]:
            add_note(CONTENT_RANGE_MEANINGLESS)

    def _parse_length(self, len_str: str, add_note: AddNoteMethodType) -> Optional[int]:
        if len_str == "*":
            add_note(CONTENT_RANGE_UNKNOWN_LENGTH)
            return None
        if not len_str.isdigit():
            add_note(RANGE_INVALID_INTEGER, value=len_str)
            return None
        return int(len_str)

    def _parse_range_spec(
        self, rng: str, add_note: AddNoteMethodType
    ) -> Tuple[Optional[int], Optional[int]]:
        if rng == "*":
            return None, None

        if "-" not in rng:
            add_note(RANGE_MISSING_HYPHEN, value=rng)
            return None, None

        first_str, last_str = rng.split("-", 1)
        if not first_str.isdigit():
            add_note(RANGE_INVALID_INTEGER, value=first_str)
            return None, None
        if not last_str.isdigit():
            add_note(RANGE_INVALID_INTEGER, value=last_str)
            return None, None

        return int(first_str), int(last_str)


class CONTENT_RANGE_MEANINGLESS(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = "This response shouldn't have a Content-Range header."
    _text = """\
HTTP only defines meaning for the `Content-Range` header in responses with a `206` (Partial
Content) or `416` (Requested Range Not Satisfiable) status code.

Because the status code is neither of those, this `Content-Range` header may confuse caches and
clients."""


class CONTENT_RANGE_MISSING_UNIT(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header is missing a unit (e.g., 'bytes')."
    _text = """\
The `Content-Range` header is missing a range unit at the start; it should 
almost always be `bytes`.

For example:

    Content-Range: bytes 1-100/200
"""


class CONTENT_RANGE_INVALID_ASTERISK(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header invalidly uses wildcards."
    _text = """\
The `Content-Range` header cannot use a wildcard (`*`) for both the range and the complete length.
"""


class CONTENT_RANGE_MISSING_SLASH(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header is missing a slash separator."
    _text = """\
The `Content-Range` header is missing a slash (`/`) separating the range from the complete length.

For example:

    Content-Range: bytes 1-100/200
"""


class RANGE_MISSING_HYPHEN(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header is missing a hyphen."
    _text = """\
The range specifier `%(value)s` is missing a hyphen separating the start and end positions."""


class RANGE_INVALID_INTEGER(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header contains a non-integer value."
    _text = """\
The value `%(value)s` is not a valid integer."""


class RANGE_INVALID(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header is invalid."
    _text = """\
The values indicated by the `Content-Range` header are not valid. The first position must be less
than or equal to the last position, and the last position must be less than the complete length."""


class CONTENT_RANGE_UNSATISFIED_BAD_SC(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = (
        "The Content-Range header indicates an unsatisfied range, but the status code is 206."
    )
    _text = """\
The `Content-Range` header uses the `*/<length>` syntax, which is reserved for `416` (Requested
Range Not Satisfiable) responses to indicate the actual length of the resource.

The `206` response status code indicates a successful range response, so this header is
incorrect."""


class CONTENT_RANGE_UNKNOWN_LENGTH(Note):
    category = categories.RANGE
    level = levels.INFO
    _summary = "The Content-Range header indicates an unknown total length."
    _text = """\
The `Content-Range` header uses `*` for the instance length, indicating that the total length of
the resource is unknown."""


class ContentRangeTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200"]
    expected_out = ContentRangeValue("bytes", 1, 100, 200)

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeUnsatisfiedTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes */1234"]
    expected_out = ContentRangeValue("bytes", None, None, 1234)

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 416  # type: ignore


class ContentRangeUnknownLengthTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 42-1233/*"]
    expected_out = ContentRangeValue("bytes", 42, 1233, None)
    expected_notes = [CONTENT_RANGE_UNKNOWN_LENGTH]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeInvalidOrderTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 100-50/200"]
    expected_out = ContentRangeValue("bytes", 100, 50, 200)
    expected_notes = [RANGE_INVALID]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeInvalidLengthTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 100-200/50"]
    expected_out = ContentRangeValue("bytes", 100, 200, 50)
    expected_notes = [RANGE_INVALID]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeSyntaxErrorTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes */*"]
    expected_out = None
    expected_notes = [CONTENT_RANGE_INVALID_ASTERISK]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 416  # type: ignore


class ContentRangeMissingUnit(FieldTest):
    name = "Content-Range"
    inputs = [b"1-100/200"]
    expected_out = None
    expected_notes = [CONTENT_RANGE_MISSING_UNIT]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeMissingHyphenTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 100/200"]
    expected_out = None
    expected_notes = [RANGE_MISSING_HYPHEN]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeInvalidIntegerTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 100-foo/200"]
    expected_out = None
    expected_notes = [RANGE_INVALID_INTEGER]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeUnsatisfiedBadSCTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes */100"]
    expected_out = ContentRangeValue("bytes", None, None, 100)
    expected_notes = [CONTENT_RANGE_UNSATISFIED_BAD_SC]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore


class ContentRangeMissingSlashTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 1-100 200"]
    expected_out = None
    expected_notes = [CONTENT_RANGE_MISSING_SLASH]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore
