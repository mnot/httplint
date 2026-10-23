from typing import Tuple

from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import ENTITY_TAG_WEAK_CASE, parse_entity_tag
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
)


class etag(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "ETag"
    description = """\
The `ETag` header provides an opaque identifier for the representation."""
    reference = f"{rfc9110.SPEC_URL}#field.etag"
    syntax = rfc9110.ETag
    category = categories.CACHING
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[bool, str]:
        return parse_entity_tag(field_value, add_note, self.suppress_syntax_note)


class ETagTest(FieldTest[AnyMessageLinterProtocol]):
    name = "ETag"
    inputs = [b'"foo"']
    expected_out = (False, "foo")


class WeakETagTest(FieldTest[AnyMessageLinterProtocol]):
    name = "ETag"
    inputs = [b'W/"foo"']
    expected_out = (True, "foo")


class UnquotedETagTest(FieldTest[AnyMessageLinterProtocol]):
    name = "ETag"
    inputs = [b"foo"]
    expected_out = (False, "foo")
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class LowerCaseWeakETagTest(FieldTest[AnyMessageLinterProtocol]):
    name = "ETag"
    inputs = [b'w/"foo"']
    expected_out = None
    expected_notes: NoteClassListType = [ENTITY_TAG_WEAK_CASE]


class LowerCaseWeakUnquotedETagTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: the case isn't the only defect, so the value gets BAD_SYNTAX, once."

    name = "ETag"
    inputs = [b"w/foo"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]
