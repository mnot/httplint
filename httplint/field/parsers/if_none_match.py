from typing import Tuple, Union

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import is_entity_tag, parse_entity_tag
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
        try:
            return parse_entity_tag(field_value)
        except ValueError:
            if is_entity_tag(field_value):  # otherwise the syntax check has reported it
                add_note(BAD_SYNTAX, ref_uri=self.reference)
            raise


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
    expected_notes: NoteClassListType = [BAD_SYNTAX]
