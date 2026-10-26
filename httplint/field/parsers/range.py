import itertools
import re
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Type

from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.common import RE_FLAGS
from httplint.field.delta_seconds import parse_digits
from httplint.field.section import FIELD_VALUE_ENCODING
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FakeRequestLinter, FieldTest
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
MAX_DIGITS = 20


class range(SingletonField[RequestLinterProtocol]):  # pylint: disable=redefined-builtin
    canonical_name = "Range"
    description = """\
The `Range` header field on a GET request modifies the method semantics to request only those
parts of the representation that are specified."""
    reference = f"{rfc9110.SPEC_URL}#field.range"
    syntax = rfc9110.Range
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
                first_byte_pos = self._parse_position(first_str, "first", add_note)

            if last_str:
                last_byte_pos = self._parse_position(last_str, "last", add_note)

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

    def _parse_position(self, value: str, which: str, add_note: AddNoteMethodType) -> int:
        result = parse_digits(value, MAX_DIGITS)
        if result is None:
            if value.isascii() and value.isdigit():
                problem = (
                    f"the {which} position in the range can't have more than {MAX_DIGITS} digits"
                )
            else:
                problem = f"the {which} position in the range must be an integer"
            self._bad_syntax(add_note, problem)
        return result

    def _bad_syntax(self, add_note: AddNoteMethodType, problem: str) -> NoReturn:
        # The value is rejected after RANGE_BAD_SYNTAX, so it doesn't need the generic note too.
        self.suppress_syntax_note()
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


class RangeTooLongBoundaryTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=" + b"9" * 21 + b"-"]
    expected_out = None
    expected_notes: NoteClassListType = [RANGE_BAD_SYNTAX]


class RangeTwentyDigitsTest(FieldTest[RequestLinterProtocol]):
    name = "Range"
    inputs = [b"bytes=" + b"9" * 20 + b"-"]
    expected_out = RangeValue("bytes", [(int("9" * 20), None)])


class RangeNoteWordingTest(unittest.TestCase):
    "Check the `problem` given to RANGE_BAD_SYNTAX, which FieldTest doesn't see."

    def problem(self, value: str) -> str:
        notes: List[Tuple[Type[Note], Dict[str, Any]]] = []
        handler = range("Range", FakeRequestLinter())

        def add_note(note: Type[Note], category: Any = None, **vrs: Any) -> Note:
            notes.append((note, vrs))
            return note("test", **vrs)

        with self.assertRaises(ValueError):
            handler.parse(value, add_note)
        self.assertEqual([n for n, _ in notes], [RANGE_BAD_SYNTAX])
        return str(notes[0][1]["problem"])

    def test_too_many_digits(self) -> None:
        self.assertIn("more than 20 digits", self.problem("bytes=" + "9" * 5000 + "-"))
        self.assertIn("last position", self.problem("bytes=0-" + "9" * 21))

    def test_non_integer(self) -> None:
        self.assertIn("must be an integer", self.problem("bytes=a-"))
        self.assertIn("must be an integer", self.problem("bytes=\xb2-"))

    def test_empty_spec(self) -> None:
        self.assertIn("empty range specifier", self.problem("bytes=0-1,"))


class RangeSyntaxHookTest(unittest.TestCase):
    """
    Guard on the note count for every short string: a value parse() rejects gets exactly
    RANGE_BAD_SYNTAX, with no generic BAD_SYNTAX on top; a value it accepts gets no syntax note,
    so the syntax regex must not reject anything parse() accepts. (parse() may still reject a
    value that matches the regex, such as "bytes=a-b".)
    """

    ALPHABET = ["=", "-", ",", " ", "\t", "0", "a", "\xa0", "\x0b", "bytes"]

    def check(self, value: str) -> None:
        notes: List[Type[Note]] = []

        def add_note(note: Type[Note], category: Any = None, **vrs: Any) -> Note:
            notes.append(note)
            return note("test", **vrs)

        handler = range("Range", FakeRequestLinter())
        handler.handle_input(value, add_note, 0)
        handler.finish(add_note)
        # RANGE_INVALID is noted as soon as a range is seen, even if a later one is rejected
        notes = [n for n in notes if n is not RANGE_INVALID]
        if handler.value is None:
            self.assertEqual(notes, [RANGE_BAD_SYNTAX], repr(value))
        else:
            self.assertNotIn(BAD_SYNTAX, notes, repr(value))
            self.assertNotIn(BAD_SYNTAX_DETAILED, notes, repr(value))
            self.assertNotIn(RANGE_BAD_SYNTAX, notes, repr(value))

    def test_short_strings(self) -> None:
        for size in (0, 1, 2, 3):
            for chars in itertools.product(self.ALPHABET, repeat=size):
                self.check("".join(chars))
        for prefix in ("bytes=", "bytes= ", "pages=", "x="):
            for size in (0, 1, 2, 3):  # not range(): the `range` class shadows it here
                for chars in itertools.product(self.ALPHABET[1:-1], repeat=size):
                    self.check(prefix + "".join(chars))
            for chars in itertools.product(self.ALPHABET[1:6], repeat=4):
                self.check(prefix + "".join(chars))
