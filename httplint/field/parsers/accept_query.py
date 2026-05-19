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


class accept_query(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Accept-Query"
    description = """\
The `Accept-Query` response header advertises which media types are accepted by the server in the
content of a QUERY request."""
    reference = (
        "https://datatracker.ietf.org/doc/html/"
        "draft-ietf-httpbis-safe-method-w-body#section-3"
    )
    syntax = False
    category = categories.GENERAL
    deprecated = False

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        return parse_media_type(
            field_value, add_note, ACCEPT_QUERY_BAD_SYNTAX, self.reference
        )


class ACCEPT_QUERY_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Query header contains a value that is not a media type."
    _text = """\
`%(value)s` is not a valid media type. `Accept-Query` is a list of media types
(e.g., `application/sparql-query`) accepted in the content of a QUERY request;
see [its definition](%(ref_uri)s) for more information."""


class AcceptQueryTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"application/sparql-query, application/sql"]
    expected_out = [("application/sparql-query", {}), ("application/sql", {})]


class AcceptQueryParamsTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"application/example;version=1"]
    expected_out = [("application/example", {"version": "1"})]


class AcceptQueryBadTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"invalid"]
    expected_out = [("invalid", {})]
    expected_notes: NoteClassListType = [ACCEPT_QUERY_BAD_SYNTAX]
