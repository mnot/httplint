from . import HttpField, FieldTest
from ..note import Note, categories, levels
from ..syntax import rfc7234
from ..type import AddNoteMethodType
from ._notes import SINGLE_HEADER_REPEAT


class age(HttpField):
    canonical_name = "Age"
    description = """\
The `Age` header conveys the sender's estimate of the amount of time since the response (or its
validation) was generated at the origin server."""
    reference = f"{rfc7234.SPEC_URL}#header.age"
    syntax = False  # rfc7234.Age
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
        return age_value


class AGE_NOT_INT(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The Age header's value should be an integer."
    text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was not an integer, so it is not a valid age."""


class AGE_NEGATIVE(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The Age headers' value must be a positive integer."
    text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was negative, so it is not a valid age."""


class AgeTest(FieldTest):
    name = "Age"
    inputs = [b"10"]
    expected_out = 10


class MultipleAgeTest(FieldTest):
    name = "Age"
    inputs = [b"20", b"10"]
    expected_out = 10
    expected_err = [SINGLE_HEADER_REPEAT]


class CharAgeTest(FieldTest):
    name = "Age"
    inputs = [b"foo"]
    expected_out = None
    expected_err = [AGE_NOT_INT]


class NegAgeTest(FieldTest):
    name = "Age"
    inputs = [b"-20"]
    expected_out = None
    expected_err = [AGE_NEGATIVE]
