from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.field.utils import check_media_type
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFListType,
)

SPEC_URL = "https://www.rfc-editor.org/rfc/rfc10008.html"


class accept_query(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Accept-Query"
    description = """\
The `Accept-Query` response header advertises which media types are accepted by the server in the
content of a QUERY request."""
    reference = f"{SPEC_URL}#section-3"
    syntax = False  # Structured Field
    category = categories.GENERAL
    deprecated = False
    sf_type = "list"
    value: SFListType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        normalised: SFListType = []
        for item in self.value:
            # SF List items are (value, parameters) tuples
            val, params = item
            if not isinstance(val, (Token, str)):
                add_note(ACCEPT_QUERY_BAD_TYPE, value=str(val))
                normalised.append(item)
                continue
            # Media type parameters are carried as SF parameters, so the item
            # value is the media range on its own. Media ranges are
            # case-insensitive, so store them lowercased, as the other
            # media-type fields do.
            media_range = str(val).lower()
            check_media_type(
                media_range,
                add_note,
                ACCEPT_QUERY_BAD_SYNTAX,
                self.reference,
                allow_wildcard=True,
                check_token=True,  # no syntax check on a Structured Field
            )
            normalised.append((type(val)(media_range), params))
        self.value = normalised


class ACCEPT_QUERY_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Query header contains a value that isn't a media range."
    _text = """\
`Accept-Query` is a List Structured Field whose members are Tokens or Strings, each
naming a media range accepted in the content of a QUERY request. `%(value)s` is
neither, so it will be ignored."""


class ACCEPT_QUERY_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Query header contains a value that is not a media range."
    _text = """\
`%(value)s` is not a valid media range. `Accept-Query` is a list of media ranges
(e.g., `application/sparql-query`, `text/*`) accepted in the content of a QUERY
request; see [its definition](%(ref_uri)s) for more information."""


class AcceptQueryTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"application/sparql-query, application/sql"]
    expected_out = [("application/sparql-query", {}), ("application/sql", {})]


class AcceptQueryStringTest(FieldTest[ResponseLinterProtocol]):
    "Media types that aren't valid Tokens have to be sent as Strings."

    name = "Accept-Query"
    inputs = [b'"application/jsonpath", "3d/example"']
    expected_out = [("application/jsonpath", {}), ("3d/example", {})]


class AcceptQueryParamsTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b'application/sql;charset="UTF-8"']
    expected_out = [("application/sql", {"charset": "UTF-8"})]


class AcceptQueryWildcardTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"*/*, text/*"]
    expected_out = [("*/*", {}), ("text/*", {})]


class AcceptQueryCaseTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b'APPLICATION/SQL, "TEXT/Plain"']
    expected_out = [("application/sql", {}), ("text/plain", {})]


class AcceptQueryBadTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"invalid"]
    expected_out = [("invalid", {})]
    expected_notes: NoteClassListType = [ACCEPT_QUERY_BAD_SYNTAX]


class AcceptQueryBadStringTest(FieldTest[ResponseLinterProtocol]):
    "A String member can carry a name that isn't a valid HTTP token."

    name = "Accept-Query"
    inputs = [b'"text/pl in"']
    expected_out = [("text/pl in", {})]
    expected_notes: NoteClassListType = [ACCEPT_QUERY_BAD_SYNTAX]


class AcceptQueryBareStarTest(FieldTest[ResponseLinterProtocol]):
    "Only */* and type/* are permitted, not a bare *."

    name = "Accept-Query"
    inputs = [b"*"]
    expected_out = [("*", {})]
    expected_notes: NoteClassListType = [ACCEPT_QUERY_BAD_SYNTAX]


class AcceptQueryBadTypeTest(FieldTest[ResponseLinterProtocol]):
    name = "Accept-Query"
    inputs = [b"123"]
    expected_out = [(123, {})]
    expected_notes: NoteClassListType = [ACCEPT_QUERY_BAD_TYPE]
