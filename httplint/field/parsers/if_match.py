from typing import Tuple, Union

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import ENTITY_TAG_LIST_STAR, ENTITY_TAG_WEAK_CASE, parse_entity_tag
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


class if_match(HttpListField[RequestLinterProtocol]):
    canonical_name = "If-Match"
    description = """\
The `If-Match` header field makes the request method conditional on the recipient origin server
having a current representation of the target resource."""
    reference = f"{rfc9110.SPEC_URL}#field.if-match"
    syntax = rfc9110.If_Match
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Union[str, Tuple[bool, str]]:
        if field_value == "*":
            return field_value
        return parse_entity_tag(field_value, add_note)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "*" in self.value and len(self.value) > 1:
            add_note(ENTITY_TAG_LIST_STAR)


class IfMatchTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'"xyzzy", "r2d2xxxx", "c3piozzzz"']
    expected_out = [(False, "xyzzy"), (False, "r2d2xxxx"), (False, "c3piozzzz")]


class IfMatchStarTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b"*"]
    expected_out = ["*"]


class IfMatchWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'W/"xyzzy", "r2d2xxxx"']
    expected_out = [(True, "xyzzy"), (False, "r2d2xxxx")]


class IfMatchLowerCaseWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'w/"xyzzy", "r2d2xxxx"']
    expected_out = [(False, "r2d2xxxx")]
    expected_notes: NoteClassListType = [BAD_SYNTAX, ENTITY_TAG_WEAK_CASE]


class IfMatchStarFirstTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'*, "a"']
    expected_out = ["*", (False, "a")]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfMatchStarLastTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'"a", *']
    expected_out = [(False, "a"), "*"]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfMatchStarWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b'W/"a", *']
    expected_out = [(True, "a"), "*"]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfMatchStarSeparateLinesTest(FieldTest[RequestLinterProtocol]):
    name = "If-Match"
    inputs = [b"*", b'"a"']
    expected_out = ["*", (False, "a")]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfMatchBadValueTest(FieldTest[RequestLinterProtocol]):
    "A bad value gets the syntax note."

    name = "If-Match"
    inputs = [b"foo"]
    expected_out = [(False, "foo")]
    expected_notes: NoteClassListType = [BAD_SYNTAX]
