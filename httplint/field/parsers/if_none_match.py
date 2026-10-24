from typing import Tuple, Union

from httplint.field import BAD_SYNTAX
from httplint.field.entity_tag import ENTITY_TAG_LIST_STAR, ENTITY_TAG_WEAK_CASE, parse_entity_tag
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, RequestLinterProtocol


class if_none_match(HttpListField[RequestLinterProtocol]):
    canonical_name = "If-None-Match"
    description = """\
The `If-None-Match` header field makes the request method conditional on the
absence of a matching entity tag, or if the field-value is "*", the absence of
any current representation of the target resource."""
    reference = f"{rfc9110.SPEC_URL}#field.if-none-match"
    syntax = rfc9110.If_None_Match
    category = categories.VALIDATION
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Union[str, Tuple[bool, str]]:
        if field_value == "*":
            return field_value
        return parse_entity_tag(field_value, add_note, self.suppress_syntax_note)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "*" in self.value and len(self.value) > 1:
            add_note(ENTITY_TAG_LIST_STAR)


class IfNoneMatchTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"']
    expected_out = [(True, "xyzzy"), (True, "r2d2xxxx"), (True, "c3piozzzz")]


class IfNoneMatchStarTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b"*"]
    expected_out = ["*"]


class IfNoneMatchStrongTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'"xyzzy"']
    expected_out = [(False, "xyzzy")]


class IfNoneMatchLowerCaseWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'w/"xyzzy"']
    expected_out = []
    expected_notes: NoteClassListType = [ENTITY_TAG_WEAK_CASE]


class IfNoneMatchStarFirstTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'*, "a"']
    expected_out = ["*", (False, "a")]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfNoneMatchStarLastTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'"a", *']
    expected_out = [(False, "a"), "*"]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfNoneMatchStarWeakTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b'W/"a", *']
    expected_out = [(True, "a"), "*"]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfNoneMatchStarSeparateLinesTest(FieldTest[RequestLinterProtocol]):
    name = "If-None-Match"
    inputs = [b"*", b'"a"']
    expected_out = ["*", (False, "a")]
    expected_notes: NoteClassListType = [ENTITY_TAG_LIST_STAR]


class IfNoneMatchBadValueTest(FieldTest[RequestLinterProtocol]):
    "A bad value gets the syntax note."

    name = "If-None-Match"
    inputs = [b"foo"]
    expected_out = [(False, "foo")]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class IfNoneMatchLowerCaseWeakUnquotedTest(FieldTest[RequestLinterProtocol]):
    "Guard: the case isn't the only defect, so only that element gets BAD_SYNTAX, once."

    name = "If-None-Match"
    inputs = [b'w/xyzzy, "r2d2xxxx"']
    expected_out = [(False, "r2d2xxxx")]
    expected_notes: NoteClassListType = [BAD_SYNTAX]
