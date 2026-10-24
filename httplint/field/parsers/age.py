from httplint.field.singleton_field import SINGLE_HEADER_REPEAT, SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import is_negative_integer, parse_delta_seconds
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9111
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)
from httplint.util import MAX_DELTA_SECONDS


class age(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Age"
    description = """\
The `Age` response header conveys the sender's estimate of the amount of time since the response
(or its validation) was generated at the origin server."""
    reference = f"{rfc9111.SPEC_URL}#field.age"
    syntax = rfc9111.Age
    category = categories.CACHING
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        # The value is a single number, so a note about it covers any syntax defect it has.
        if is_negative_integer(field_value):
            self.suppress_syntax_note()
            add_note(AGE_NEGATIVE)
            raise ValueError
        # Generous digit bound: oversized values still get AGE_LARGE, not AGE_NOT_INT.
        parsed = parse_delta_seconds(field_value, add_note, AGE_NOT_INT, max_digits=4000)
        if parsed is None:
            self.suppress_syntax_note()
            raise ValueError
        age_value = parsed
        if age_value > MAX_DELTA_SECONDS:
            add_note(AGE_LARGE)
        return age_value


class AGE_NOT_INT(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The Age header's value should be an integer."
    _text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was not an integer, so it is not a valid age."""


class AGE_NEGATIVE(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The Age headers' value must be a positive integer."
    _text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was negative, so it is not a valid age."""


class AGE_LARGE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The Age header's value is very large."
    _text = """\
The `Age` header's value is greater than 2,147,483,648. Some implementations may represent it
using that value (which is over 68 years).
"""


class AgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"10"]
    expected_out = 10


class MultipleAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"20", b"10"]
    expected_out = 20
    expected_notes: NoteClassListType = [SINGLE_HEADER_REPEAT]


class CharAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"foo"]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NOT_INT]


class NegAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"-20"]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NEGATIVE]


class BigAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"2147483649"]
    expected_out = 2147483649
    expected_notes: NoteClassListType = [AGE_LARGE]


class UnderscoreAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"1_0"]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NOT_INT]


class PlusAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"+1"]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NOT_INT]


class NegativeZeroAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"-0"]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NEGATIVE]


class HugeAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"9" * 5000]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NOT_INT]


class MaxDigitsAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"9" * 4000]
    expected_out = int("9" * 4000)
    expected_notes: NoteClassListType = [AGE_LARGE]


class OverMaxDigitsAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Age"
    inputs = [b"9" * 4001]
    expected_out = None
    expected_notes: NoteClassListType = [AGE_NOT_INT]
