from typing import NamedTuple, Optional

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.notes import BAD_SYNTAX
from httplint.message import HttpMessageLinter, HttpResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class ContentRangeValue(NamedTuple):
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
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Optional[ContentRangeValue]:
        # #53: check syntax, values?
        if isinstance(
            self.message, HttpResponseLinter
        ) and self.message.status_code not in [
            206,
            416,
        ]:
            add_note(CONTENT_RANGE_MEANINGLESS)

        try:
            unit, rest = field_value.split(" ", 1)
            rng, len_str = rest.split("/", 1)
        except ValueError:
            return None

        first_byte_pos: Optional[int] = None
        last_byte_pos: Optional[int] = None
        complete_length: Optional[int] = None

        if len_str != "*":
            if not len_str.isdigit():
                return None
            complete_length = int(len_str)

        if rng == "*":
            if complete_length is None:
                # "*/" complete-length
                return None
        else:
            if "-" not in rng:
                return None
            first_str, last_str = rng.split("-", 1)
            if not first_str.isdigit() or not last_str.isdigit():
                return None
            first_byte_pos = int(first_str)
            last_byte_pos = int(last_str)

            if first_byte_pos > last_byte_pos:
                # invalid range
                add_note(RANGE_INVALID)

            if complete_length is not None and last_byte_pos >= complete_length:
                # invalid range
                add_note(RANGE_INVALID)

        return ContentRangeValue(unit, first_byte_pos, last_byte_pos, complete_length)


class CONTENT_RANGE_MEANINGLESS(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = "This response shouldn't have a Content-Range header."
    _text = """\
HTTP only defines meaning for the `Content-Range` header in responses with a `206` (Partial
Content) or `416` (Requested Range Not Satisfiable) status code.

Because the status code is neither of those, this `Content-Range` header may confuse caches and
clients."""


class RANGE_INVALID(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header is invalid."
    _text = """\
The values indicated by the `Content-Range` header are not valid. The first position must be less
than or equal to the last position, and the last position must be less than the complete length."""


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
    expected_notes = [BAD_SYNTAX]

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 416  # type: ignore
