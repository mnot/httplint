import re
from typing import Any

from httplint.field import BAD_SYNTAX
from httplint.field.date_field import HttpDateField
from httplint.field.tests import FieldTest
from httplint.field.utils import (
    BAD_DATE_SYNTAX,
    DATE_OBSOLETE,
    RE_FLAGS,
    is_entity_tag,
    parse_entity_tag,
)
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


class if_range(HttpDateField[RequestLinterProtocol]):
    canonical_name = "If-Range"
    description = """\
The `If-Range` header field allows a client to "short-circuit" the second request. It means: if
the representation is unchanged, send me the part(s) that I am missing; otherwise, send me the
entire new representation."""
    reference = f"{rfc9110.SPEC_URL}#field.if-range"
    category = categories.VALIDATION
    deprecated = False

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Any:  # int, or (weak, opaque-tag)
        # The value is an entity-tag or an HTTP-date; no date starts with a quote or "W/".
        if not re.match(r'(?:"|W/)', field_value, RE_FLAGS):
            return super().parse(field_value, add_note)
        try:
            tag = parse_entity_tag(field_value)
        except ValueError:
            tag = None
        if tag is None or not is_entity_tag(field_value):
            add_note(BAD_SYNTAX, ref_uri=self.reference)
        if tag is None:
            raise ValueError
        return tag


class IfRangeTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'"xyzzy"']
    expected_out = (False, "xyzzy")


class IfRangeWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'W/"xyzzy"']
    expected_out = (True, "xyzzy")


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
    name = "If-Range"
    inputs = [b"yesterday"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class IfRangeUnterminatedTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'"xyzzy']
    expected_out = (False, '"xyzzy')
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfRangeLowerCaseWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Range"
    inputs = [b'w/"xyzzy"']
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]
