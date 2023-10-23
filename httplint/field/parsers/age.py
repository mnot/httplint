from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9111
from httplint.types import AddNoteMethodType
from httplint.field.notes import SINGLE_HEADER_REPEAT


class age(HttpField):
    canonical_name = "Age"
    description = """\
The `Age` response header conveys the sender's estimate of the amount of time since the response
(or its validation) was generated at the origin server."""
    reference = f"{rfc9111.SPEC_URL}#field.age"
    syntax = False  # rfc9111.Age
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        try:
            age_value = int(field_value)
        except ValueError:
            add_note(AGE_NOT_INT)
            raise
        if age_value < 0:
            add_note(AGE_NEGATIVE)
            raise ValueError
        if age_value > 2147483648:
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


class AgeTest(FieldTest):
    name = "Age"
    inputs = [b"10"]
    expected_out = 10


class MultipleAgeTest(FieldTest):
    name = "Age"
    inputs = [b"20", b"10"]
    expected_out = 10
    expected_notes = [SINGLE_HEADER_REPEAT]


class CharAgeTest(FieldTest):
    name = "Age"
    inputs = [b"foo"]
    expected_out = None
    expected_notes = [AGE_NOT_INT]


class NegAgeTest(FieldTest):
    name = "Age"
    inputs = [b"-20"]
    expected_out = None
    expected_notes = [AGE_NEGATIVE]


class BigAgeTest(FieldTest):
    name = "Age"
    inputs = [b"2147483649"]
    expected_out = 2147483649
    expected_notes = [AGE_LARGE]
