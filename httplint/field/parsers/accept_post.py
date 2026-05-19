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


class accept_post(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Accept-Post"
    description = """\
The `Accept-Post` response header advertises which media types are accepted by the server in a
POST request."""
    reference = "https://www.w3.org/TR/ldp/#header-accept-post"
    syntax = False
    category = categories.GENERAL
    deprecated = False

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        return parse_media_type(
            field_value,
            add_note,
            ACCEPT_POST_BAD_SYNTAX,
            self.reference,
            allow_wildcard=True,
        )


class ACCEPT_POST_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Post header contains a value that is not a media type."
    _text = """\
`%(value)s` is not a valid media type. `Accept-Post` is a list of media types
(e.g., `text/turtle`) accepted in a POST request; see [its definition](%(ref_uri)s)
for more information."""


class AcceptPostTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Post"
    inputs = [b"text/turtle, application/ld+json"]
    expected_out = [("text/turtle", {}), ("application/ld+json", {})]


class AcceptPostWildcardTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Post"
    inputs = [b"*/*"]
    expected_out = [("*/*", {})]


class AcceptPostBadTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Post"
    inputs = [b"invalid"]
    expected_out = [("invalid", {})]
    expected_notes: NoteClassListType = [ACCEPT_POST_BAD_SYNTAX]
