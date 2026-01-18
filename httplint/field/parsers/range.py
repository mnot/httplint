from dataclasses import dataclass
from typing import List, Tuple, Optional

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


@dataclass
class RangeValue:
    unit: str
    ranges: List[Tuple[Optional[int], Optional[int]]]


class range(SingletonField):  # pylint: disable=redefined-builtin
    canonical_name = "Range"
    description = """\
The `Range` header field on a GET request modifies the method semantics to request only those
parts of the representation that are specified."""
    reference = f"{rfc9110.SPEC_URL}#field.range"
    syntax = rfc9110.Range
    report_syntax = False
    category = categories.RANGE
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Optional[RangeValue]:
        try:
            unit, rest = field_value.split("=", 1)
        except ValueError:
            raise

        ranges: List[Tuple[Optional[int], Optional[int]]] = []
        for rng in rest.split(","):
            rng = rng.strip()
            if "-" not in rng:
                add_note(
                    RANGE_BAD_SYNTAX,
                    ref_uri=self.reference,
                    problem="the range specifier must contain a hyphen",
                )
                raise ValueError

            first_str, last_str = rng.split("-", 1)
            first_byte_pos: Optional[int] = None
            last_byte_pos: Optional[int] = None

            if first_str:
                if not first_str.isdigit():
                    add_note(
                        RANGE_BAD_SYNTAX,
                        ref_uri=self.reference,
                        problem="the first position in the range must be an integer",
                    )
                    raise ValueError
                first_byte_pos = int(first_str)

            if last_str:
                if not last_str.isdigit():
                    add_note(
                        RANGE_BAD_SYNTAX,
                        ref_uri=self.reference,
                        problem="the last position in the range must be an integer",
                    )
                    raise ValueError
                last_byte_pos = int(last_str)

            if first_byte_pos is None and last_byte_pos is None:
                add_note(
                    RANGE_BAD_SYNTAX,
                    ref_uri=self.reference,
                    problem="at least one of the first or last positions must be specified",
                )
                raise ValueError

            if (
                first_byte_pos is not None
                and last_byte_pos is not None
                and first_byte_pos > last_byte_pos
            ):
                add_note(RANGE_INVALID)

            ranges.append((first_byte_pos, last_byte_pos))

        return RangeValue(unit, ranges)


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


class RangeTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=0-499"]
    expected_out = RangeValue("bytes", [(0, 499)])


class RangeMultiTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=0-499, 500-"]
    expected_out = RangeValue("bytes", [(0, 499), (500, None)])


class RangeSuffixTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=-500"]
    expected_out = RangeValue("bytes", [(None, 500)])


class RangeInvalidTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=0-0, -1"]
    expected_out = RangeValue("bytes", [(0, 0), (None, 1)])


class RangeInvalidOrderTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=500-100"]
    expected_out = RangeValue("bytes", [(500, 100)])
    expected_notes = [RANGE_INVALID]


class RangeSyntaxErrorTest(FieldTest):
    name = "Range"
    inputs = [b"bytes=a-b"]
    expected_out = None
    expected_notes = [RANGE_BAD_SYNTAX]


class RangeNoSplitTest(FieldTest):
    name = "Range"
    inputs = [b"bytes"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]
