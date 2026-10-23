from httplint.field.cors import CORS_PREFLIGHT_ONLY
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_delta_seconds
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)


class access_control_max_age(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Access-Control-Max-Age"
    description = """\
The `Access-Control-Max-Age` response header indicates how long the results of a CORS preflight
request (as scoped by the `Access-Control-Allow-Methods` and
`Access-Control-Allow-Headers` request headers) can be cached."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-max-age"
    syntax = rfc9110.delay_seconds
    report_syntax = False
    category = categories.CORS
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        if field_value.startswith("-") and field_value[1:].isascii() and field_value[1:].isdigit():
            add_note(CORS_MAX_AGE_NEGATIVE, ref_uri=self.reference)
            raise ValueError
        val = parse_delta_seconds(
            field_value, add_note, CORS_MAX_AGE_INVALID, ref_uri=self.reference
        )
        if val is None:
            raise ValueError
        return val


class CORS_MAX_AGE_INVALID(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "Access-Control-Max-Age must be an integer."
    _text = """\
The `Access-Control-Max-Age` header indicates how many seconds a preflight response can be cached
for. It must be a non-negative integer."""


class CORS_MAX_AGE_NEGATIVE(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "Access-Control-Max-Age must be non-negative."
    _text = """\
The `Access-Control-Max-Age` header indicates how many seconds a preflight response can be cached
for. It cannot be less than zero."""


class AccessControlMaxAgeTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"123"]
    expected_out = 123
    expected_notes: NoteClassListType = [CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgeInvalidTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"abc"]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_INVALID, CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgeNegativeTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"-1"]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_NEGATIVE, CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgeUnderscoreTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"1_0"]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_INVALID, CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgePlusTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"+5"]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_INVALID, CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgeNegativeZeroTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"-0"]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_NEGATIVE, CORS_PREFLIGHT_ONLY]


class AccessControlMaxAgeHugeTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Max-Age"
    inputs = [b"9" * 5000]
    expected_out = None
    expected_notes: NoteClassListType = [CORS_MAX_AGE_INVALID, CORS_PREFLIGHT_ONLY]
