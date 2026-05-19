from typing import Tuple

from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_media_type
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ParamDictType,
    ResponseLinterProtocol,
)


class accept_patch(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Accept-Patch"
    description = """\
The `Accept-Patch` response header advertises which media types are accepted by the server in a
PATCH request."""
    reference = "https://www.rfc-editor.org/rfc/rfc5789.html#section-3.1"
    syntax = False
    category = categories.GENERAL
    deprecated = False

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        return parse_media_type(
            field_value, add_note, ACCEPT_PATCH_BAD_SYNTAX, self.reference
        )


class ACCEPT_PATCH_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Patch header isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""


class AcceptPatchTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Patch"
    inputs = [b"application/json-patch+json, application/merge-patch+json"]
    expected_out = [
        ("application/json-patch+json", {}),
        ("application/merge-patch+json", {}),
    ]


class AcceptPatchParamsTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Patch"
    inputs = [b"text/example;charset=utf-8"]
    expected_out = [("text/example", {"charset": "utf-8"})]


class AcceptPatchBadTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Patch"
    inputs = [b"invalid"]
    expected_out = [("invalid", {})]
    expected_notes: NoteClassListType = [ACCEPT_PATCH_BAD_SYNTAX]
