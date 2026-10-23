import re
import unittest
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
    Type,
)

from httplint.field import BAD_SYNTAX
from httplint.field.section import FIELD_VALUE_ENCODING
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FakeResponseLinter, FieldTest
from httplint.field.utils import RE_FLAGS, parse_digits
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)


@dataclass
class ContentRangeValue:
    unit: str
    first_byte_pos: Optional[int]
    last_byte_pos: Optional[int]
    complete_length: Optional[int]


UNIT_RE = re.compile(rfc9110.range_unit, RE_FLAGS)
MISSING_UNIT_RE = re.compile(r"(?:[0-9]+-[0-9]+|\*)/(?:[0-9]+|\*)")
WHITESPACE_RE = re.compile(r"\s")
MAX_DIGITS = 20
EXCERPT_CHARS = 40


def excerpt(value: str) -> str:
    "Shorten a wire value so that a hostile one doesn't bloat a note."
    if len(value) > EXCERPT_CHARS:
        return value[:EXCERPT_CHARS] + "..."
    return value


class content_range(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Content-Range"
    description = """\
The `Content-Range` response header is sent in a `206` (Partial Content) response to indicate
where in the full response content the partial content is located. It is also used
in `416` (Requested Range Not Satisfiable) responses."""
    reference = f"{rfc9110.SPEC_URL}#field.content-range"
    syntax = rfc9110.Content_Range
    # parse() reports syntax problems itself, and always rejects the value after BAD_SYNTAX, so
    # that one defect gives one note (the more specific notes cover the other defects).
    report_syntax = False
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Optional[ContentRangeValue]:
        self._check_status(add_note)

        unit, sep, rest = field_value.partition(" ")
        if not sep:
            if MISSING_UNIT_RE.fullmatch(field_value):
                add_note(CONTENT_RANGE_MISSING_UNIT)
                raise ValueError
            self._bad_syntax(add_note)
        if not UNIT_RE.fullmatch(unit):
            self._bad_syntax(add_note)

        try:
            rng, len_str = rest.split("/", 1)
        except ValueError:
            add_note(CONTENT_RANGE_MISSING_SLASH)
            raise

        # Empty parts and stray whitespace aren't covered by the more specific notes below
        if not rng or not len_str or WHITESPACE_RE.search(rng + len_str):
            self._bad_syntax(add_note)

        if rng == "*" and len_str == "*":
            add_note(CONTENT_RANGE_INVALID_ASTERISK)
            raise ValueError

        complete_length = self._parse_length(len_str, add_note)
        if complete_length is None and len_str != "*":
            # length parsing failed; already noted
            raise ValueError

        first_byte_pos, last_byte_pos = self._parse_range_spec(rng, add_note)

        if rng == "*":
            if self._status_code() == 206:
                add_note(CONTENT_RANGE_UNSATISFIED_BAD_SC)
        elif first_byte_pos is None:
            # Error in range parsing; already noted
            raise ValueError
        else:
            if self._status_code() == 416:
                add_note(CONTENT_RANGE_SATISFIED_IN_416)
            if last_byte_pos is not None:
                if first_byte_pos > last_byte_pos:
                    add_note(RANGE_INVALID)
                if complete_length is not None and last_byte_pos >= complete_length:
                    add_note(RANGE_INVALID)

        return ContentRangeValue(unit, first_byte_pos, last_byte_pos, complete_length)

    def _bad_syntax(self, add_note: AddNoteMethodType) -> NoReturn:
        add_note(BAD_SYNTAX, ref_uri=self.reference)
        raise ValueError

    def _status_code(self) -> Optional[int]:
        if getattr(self.message, "message_type", None) == "response":
            return self.message.status_code
        return None

    def _check_status(self, add_note: AddNoteMethodType) -> None:
        if getattr(self.message, "message_type", None) == "response":
            if self._status_code() not in [206, 416]:
                add_note(CONTENT_RANGE_MEANINGLESS)

    def _parse_length(self, len_str: str, add_note: AddNoteMethodType) -> Optional[int]:
        if len_str == "*":
            add_note(CONTENT_RANGE_UNKNOWN_LENGTH)
            return None
        return self._parse_integer(len_str, add_note)

    def _parse_integer(self, value: str, add_note: AddNoteMethodType) -> Optional[int]:
        result = parse_digits(value, MAX_DIGITS)
        if result is None:
            if value.isascii() and value.isdigit():
                add_note(RANGE_INTEGER_TOO_LONG, value=excerpt(value), max_digits=MAX_DIGITS)
            else:
                add_note(RANGE_INVALID_INTEGER, value=excerpt(value))
        return result

    def _parse_range_spec(
        self, rng: str, add_note: AddNoteMethodType
    ) -> Tuple[Optional[int], Optional[int]]:
        if rng == "*":
            return None, None

        if "-" not in rng:
            add_note(RANGE_MISSING_HYPHEN, value=excerpt(rng))
            return None, None

        first_str, last_str = rng.split("-", 1)
        if not first_str or not last_str:
            self._bad_syntax(add_note)
        first = self._parse_integer(first_str, add_note)
        if first is None:
            return None, None
        last = self._parse_integer(last_str, add_note)
        if last is None:
            return None, None

        return first, last


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


class RANGE_INTEGER_TOO_LONG(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Content-Range header contains an integer with too many digits."
    _text = """\
The value `%(value)s` has more than %(max_digits)s digits, which is more than recipients can be
expected to handle."""


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


class CONTENT_RANGE_SATISFIED_IN_416(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = "A 416 response should use the unsatisfied-range form of Content-Range."
    _text = """\
When a `416` (Range Not Satisfiable) response includes a `Content-Range` header, it should use
the `bytes */<length>` form, which tells the client how long the representation currently is.

This response uses a range that was satisfied (like `bytes 1-100/200`), which is how a `206`
(Partial Content) response is described, so clients may not know why their range failed."""


class CONTENT_RANGE_UNKNOWN_LENGTH(Note):
    category = categories.RANGE
    level = levels.INFO
    _summary = "The Content-Range header indicates an unknown total length."
    _text = """\
The `Content-Range` header uses `*` for the instance length, indicating that the total length of
the resource is unknown."""


class ContentRangeTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200"]
    expected_out = ContentRangeValue("bytes", 1, 100, 200)

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeUnsatisfiedTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes */1234"]
    expected_out = ContentRangeValue("bytes", None, None, 1234)

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 416


class ContentRangeUnknownLengthTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 42-1233/*"]
    expected_out = ContentRangeValue("bytes", 42, 1233, None)
    expected_notes: NoteClassListType = [CONTENT_RANGE_UNKNOWN_LENGTH]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeInvalidOrderTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 100-50/200"]
    expected_out = ContentRangeValue("bytes", 100, 50, 200)
    expected_notes: NoteClassListType = [RANGE_INVALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeInvalidLengthTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 100-200/50"]
    expected_out = ContentRangeValue("bytes", 100, 200, 50)
    expected_notes: NoteClassListType = [RANGE_INVALID]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeSyntaxErrorTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes */*"]
    expected_out = None
    expected_notes: NoteClassListType = [CONTENT_RANGE_INVALID_ASTERISK]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 416


class ContentRangeMissingUnit(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"1-100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [CONTENT_RANGE_MISSING_UNIT]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeMissingHyphenTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_MISSING_HYPHEN]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeInvalidIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 100-foo/200"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INVALID_INTEGER]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeUnsatisfiedBadSCTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes */100"]
    expected_out = ContentRangeValue("bytes", None, None, 100)
    expected_notes: NoteClassListType = [CONTENT_RANGE_UNSATISFIED_BAD_SC]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeMissingSlashTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100 200"]
    expected_out = None
    expected_notes: NoteClassListType = [CONTENT_RANGE_MISSING_SLASH]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeTabAfterUnitTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes\t1-100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeDoubleSpaceTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes  1-100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeTrailingTokenTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200 extra"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeNoUnitNoSpaceTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeBadUnitTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"by(tes 1-100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeEmptyFirstTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes -100/200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeEmptyLastTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-/200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeEmptyLengthTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeEmptyRangeTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes /200"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeSatisfiedIn416Test(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200"]
    expected_out = ContentRangeValue("bytes", 1, 100, 200)
    expected_notes: NoteClassListType = [CONTENT_RANGE_SATISFIED_IN_416]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 416


class ContentRangeHugeFirstTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes " + b"1" * 5000 + b"-6000/7000"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INTEGER_TOO_LONG]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeHugeLastTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-" + b"9" * 5000 + b"/7000"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INTEGER_TOO_LONG]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeHugeLengthTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/" + b"9" * 5000]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INTEGER_TOO_LONG]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeSuperscriptTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/\xb2"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INVALID_INTEGER, FIELD_VALUE_ENCODING]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeTooLongBoundaryTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/" + b"9" * 21]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_INTEGER_TOO_LONG]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeTwentyDigitsTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Range"
    inputs = [b"bytes 1-100/" + b"9" * 20]
    expected_out = ContentRangeValue("bytes", 1, 100, int("9" * 20))

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.status_code = 206


class ContentRangeNoteWordingTest(unittest.TestCase):
    "Check the variables the integer and hyphen notes are given, which FieldTest doesn't see."

    def parse(self, value: str) -> List[Tuple[Type[Note], Dict[str, Any]]]:
        message = FakeResponseLinter()
        message.status_code = 206
        notes: List[Tuple[Type[Note], Dict[str, Any]]] = []
        handler = content_range("Content-Range", message)

        def add_note(note: Type[Note], category: Any = None, **vrs: Any) -> Note:
            notes.append((note, vrs))
            return note("test", **vrs)

        with self.assertRaises(ValueError):
            handler.parse(value, add_note)
        return notes

    def test_too_long(self) -> None:
        notes = self.parse("bytes 1-100/" + "9" * 5000)
        self.assertEqual([n for n, _ in notes], [RANGE_INTEGER_TOO_LONG])
        value = notes[0][1]["value"]
        self.assertTrue(value.startswith("9" * 40))
        self.assertLess(len(value), 50)
        self.assertEqual(notes[0][1]["max_digits"], 20)

    def test_invalid_shortened(self) -> None:
        notes = self.parse("bytes 1-100/" + "x" * 5000)
        self.assertEqual([n for n, _ in notes], [RANGE_INVALID_INTEGER])
        self.assertLess(len(notes[0][1]["value"]), 50)

    def test_hyphen_shortened(self) -> None:
        notes = self.parse("bytes " + "1" * 5000 + "/200")
        self.assertEqual([n for n, _ in notes], [RANGE_MISSING_HYPHEN])
        self.assertLess(len(notes[0][1]["value"]), 50)

    def test_short_unchanged(self) -> None:
        notes = self.parse("bytes 1-100/abc")
        self.assertEqual(notes, [(RANGE_INVALID_INTEGER, {"value": "abc"})])
