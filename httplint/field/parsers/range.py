import re
from dataclasses import dataclass, field
from typing import List, NoReturn, Optional, Tuple

from httplint.field.section import FIELD_VALUE_ENCODING
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import RE_FLAGS, parse_digits
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


@dataclass
class RangeValue:
    unit: str
    ranges: List[Tuple[Optional[int], Optional[int]]]
    other_ranges: List[str] = field(default_factory=list)  # range-specs, for non-bytes units


RANGE_UNIT_RE = re.compile(rfc9110.range_unit, RE_FLAGS)
OTHER_RANGE_RE = re.compile(rfc9110.other_range, RE_FLAGS)
OWS = " \t"


class range(SingletonField[RequestLinterProtocol]):  # pylint: disable=redefined-builtin
    canonical_name = "Range"
    description = """\
The `Range` header field on a GET request modifies the method semantics to request only those
parts of the representation that are specified."""
    reference = f"{rfc9110.SPEC_URL}#field.range"
    syntax = rfc9110.Range
    report_syntax = False
    category = categories.RANGE
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Optional[RangeValue]:
        unit, sep, rest = field_value.partition("=")
        if not sep:
            self._bad_syntax(add_note, "the range specifier must contain an equals sign")
        if not RANGE_UNIT_RE.fullmatch(unit):
            self._bad_syntax(add_note, "the range unit must be a token")

        if unit.lower() != "bytes":
            return self._parse_other(unit, rest, add_note)

        ranges: List[Tuple[Optional[int], Optional[int]]] = []
        for rng in rest.split(","):
            rng = rng.strip(OWS)
            if not rng:
                self._bad_syntax(
                    add_note, "the range set must not contain an empty range specifier"
                )
            if "-" not in rng:
                self._bad_syntax(add_note, "the range specifier must contain a hyphen")

            first_str, last_str = rng.split("-", 1)
            first_byte_pos: Optional[int] = None
            last_byte_pos: Optional[int] = None

            if first_str:
                first_byte_pos = parse_digits(first_str)
                if first_byte_pos is None:
                    self._bad_syntax(add_note, "the first position in the range must be an integer")

            if last_str:
                last_byte_pos = parse_digits(last_str)
                if last_byte_pos is None:
                    self._bad_syntax(add_note, "the last position in the range must be an integer")

            if first_byte_pos is None and last_byte_pos is None:
                self._bad_syntax(
                    add_note, "at least one of the first or last positions must be specified"
                )

            if (
                first_byte_pos is not None
                and last_byte_pos is not None
                and first_byte_pos > last_byte_pos
            ):
                add_note(RANGE_INVALID)

            ranges.append((first_byte_pos, last_byte_pos))

        return RangeValue(unit, ranges)

    def _parse_other(
        self, unit: str, rest: str, add_note: AddNoteMethodType
    ) -> Optional[RangeValue]:
        "Range units other than bytes: each range-spec is an opaque other-range."
        other_ranges: List[str] = []
        for rng in rest.split(","):
            rng = rng.strip(OWS)
            if not rng:
                self._bad_syntax(
                    add_note, "the range set must not contain an empty range specifier"
                )
            if not OTHER_RANGE_RE.fullmatch(rng):
                self._bad_syntax(
                    add_note, "the range specifier contains a character that isn't allowed"
                )
            other_ranges.append(rng)
        return RangeValue(unit, [], other_ranges)

    def _bad_syntax(self, add_note: AddNoteMethodType, problem: str) -> NoReturn:
        add_note(RANGE_BAD_SYNTAX, ref_uri=self.reference, problem=problem)
        raise ValueError


class RANGE_INVALID(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Range header is invalid."
    _text = """\
The values indicated by the `Range` header are not valid. The first position must be less
than or equal to the last position."""


class RANGE_BAD_SYNTAX(Note):
    category = categories.RANGE
    level = levels.BAD
    _summary = "The Range header value isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; %(problem)s.

See [its definition](%(ref_uri)s) for more information."""


class RangeTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=0-499"]
    expected_out = RangeValue("bytes", [(0, 499)])


class RangeMultiTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=0-499, 500-"]
    expected_out = RangeValue("bytes", [(0, 499), (500, None)])


class RangeSuffixTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=-500"]
    expected_out = RangeValue("bytes", [(None, 500)])


class RangeInvalidTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=0-0, -1"]
    expected_out = RangeValue("bytes", [(0, 0), (None, 1)])


class RangeInvalidOrderTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=500-100"]
    expected_out = RangeValue("bytes", [(500, 100)])
    expected_notes: NoteClassListType = [RANGE_INVALID]


class RangeSyntaxErrorTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=a-b"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeNoSplitTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeOtherUnitTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"pages=1-3, 5"]
    expected_out = RangeValue("pages", [], ["1-3", "5"])


class RangeOtherUnitSingleTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"pages=1"]
    expected_out = RangeValue("pages", [], ["1"])


class RangeUnitCaseTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"Bytes=0-1"]
    expected_out = RangeValue("Bytes", [(0, 1)])


class RangeOtherUnitBadCharTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b'pages=a"b c']
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeEmptyUnitTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"=0-1"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeBadUnitTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"by(tes=0-1"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeEmptySetTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes="]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeEmptySpecTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=0-1,"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeEmptyOtherSpecTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"pages=1,,2"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeNoPositionsTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=-"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeHugeDigitsTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=" + b"1" * 5000 + b"-"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeHugeLastDigitsTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=0-" + b"9" * 5000]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeSuperscriptTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=\xb2-"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX, FIELD_VALUE_ENCODING]
