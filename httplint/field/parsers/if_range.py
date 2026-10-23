import re
from typing import Tuple, Union

from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import (
    BAD_DATE_SYNTAX,
    DATE_OBSOLETE,
    ENTITY_TAG_WEAK_CASE,
    RE_FLAGS,
    is_entity_tag,
    parse_entity_tag,
    parse_http_date,
)
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


class if_range(SingletonField[RequestLinterProtocol]):
    canonical_name = "If-Range"
    description = """\
The `If-Range` header field allows a client to "short-circuit" the second request. It means: if
the representation is unchanged, send me the part(s) that I am missing; otherwise, send me the
entire new representation."""
    reference = f"{rfc9110.SPEC_URL}#field.if-range"
    syntax = False  # parse() checks both arms
    category = categories.VALIDATION
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Union[int, Tuple[bool, str]]:
        "If-Range = entity-tag / HTTP-date; returns the date, or (weak, opaque-tag)."
        # An entity-tag starts with a quote or "W/", and an HTTP-date with a day name.
        if re.match(r'(?:"|W/)', field_value, RE_FLAGS):
            if not is_entity_tag(field_value):
                add_note(BAD_SYNTAX, ref_uri=self.reference)
            tag = parse_entity_tag(field_value, add_note)
            if tag[0]:
                add_note(IF_RANGE_WEAK)
            return tag
        if re.match(rfc9110.day_name, field_value, RE_FLAGS):
            return parse_http_date(field_value, add_note, category=self.category)
        add_note(BAD_SYNTAX, ref_uri=self.reference)
        raise ValueError


class IF_RANGE_WEAK(Note):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "The %(field_name)s header's entity tag is weak."
    _text = """\
[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-range) says that a client must
not send a weak entity tag in `If-Range`. Because the comparison it requires is a strong one, a
server will never find a weak tag to match, so the whole representation is sent instead of the
range requested."""


class IfRangeTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'"xyzzy"']
    expected_out = (False, "xyzzy")


class IfRangeWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'W/"xyzzy"']
    expected_out = (True, "xyzzy")
    expected_notes: NoteClassListType = [IF_RANGE_WEAK]


class IfRangeDateTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = 783459811


class IfRangeObsoleteDateTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b"Saturday, 29-Oct-94 19:43:31 GMT"]
    expected_out = 783459811
    expected_notes: NoteClassListType = [DATE_OBSOLETE]


class IfRangeBadDateTest(FieldTest[RequestLinterProtocol]):
    "Starts like a date, so it's reported as one."

    name = "If-Range"
    inputs = [b"Mon, 31 Feb 2011 25:61:61 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class IfRangeUnquotedTest(FieldTest[RequestLinterProtocol]):
    "Neither an entity-tag nor a date."

    name = "If-Range"
    inputs = [b"xyzzy"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfRangeEmptyTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b""]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfRangeDigitsTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b"0"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfRangeUnterminatedTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'"xyzzy']
    expected_out = (False, '"xyzzy')
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfRangeLowerCaseWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'w/"xyzzy"']
    expected_out = None
    expected_notes: NoteClassListType = [ENTITY_TAG_WEAK_CASE]


class IfRangeLowerCaseWeakUnquotedTest(FieldTest[RequestLinterProtocol]):
    "One note for the unquoted tag; the case of the prefix isn't also reported."

    name = "If-Range"
    inputs = [b"w/xyzzy"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]
