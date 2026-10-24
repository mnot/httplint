from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, ResponseLinterProtocol

MAX_SERVER_LENGTH = 64


class server(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Server"
    description = """\
The `Server` response header contains information about the software used by the origin server to
handle the request."""
    reference = f"{rfc9110.SPEC_URL}#field.server"
    syntax = rfc9110.Server
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if len(field_value) > MAX_SERVER_LENGTH:
            add_note(
                SERVER_TOO_LONG,
                server_string=field_value,
                server_length=f"{len(field_value):,} bytes",
            )
        return field_value


class ServerTest(FieldTest[ResponseLinterProtocol]):
    name = "Server"
    inputs = [b"Apache/2.4.1 (Unix)"]
    expected_out = "Apache/2.4.1 (Unix)"
    expected_notes: NoteClassListType = []


class ServerPlainTest(FieldTest[ResponseLinterProtocol]):
    name = "Server"
    inputs = [b"CERN/3.0 libwww/2.17"]
    expected_out = "CERN/3.0 libwww/2.17"
    expected_notes: NoteClassListType = []


class ServerCommentCommaTest(FieldTest[ResponseLinterProtocol]):
    "A comma inside a comment doesn't split the value."

    name = "Server"
    inputs = [b"Apache/2.4.1 (Unix, Linux)"]
    expected_out = "Apache/2.4.1 (Unix, Linux)"
    expected_notes: NoteClassListType = []


class ServerNestedCommentTest(FieldTest[ResponseLinterProtocol]):
    "Comments nested to the three levels the syntax rule allows stay in one value."

    name = "Server"
    inputs = [b"a (b (c (d, e), f), g)"]
    expected_out = "a (b (c (d, e), f), g)"
    expected_notes: NoteClassListType = []


class SERVER_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The Server header is long."
    _text = """\
The `Server` header is %(server_length)s long, which uses unnecessary bandwidth
and can expose details of the back-end system to attackers.

Consider shortening it."""


class ServerTooLongTest(FieldTest[ResponseLinterProtocol]):
    name = "Server"
    inputs = [b"a" * (MAX_SERVER_LENGTH + 1)]
    expected_out = "a" * (MAX_SERVER_LENGTH + 1)
    expected_notes: NoteClassListType = [SERVER_TOO_LONG]
