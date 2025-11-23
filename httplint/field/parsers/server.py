from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


MAX_SERVER_LENGTH = 64


class server(HttpField):
    canonical_name = "Server"
    description = """\
The `Server` response header contains information about the software used by the origin server to
handle the request."""
    reference = f"{rfc9110.SPEC_URL}#field.server"
    syntax = rfc9110.Server
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if len(field_value) > MAX_SERVER_LENGTH:
            add_note(
                SERVER_TOO_LONG,
                server_string=field_value,
                server_length=f"{len(field_value):,} bytes",
            )
        return field_value


class ServerTest(FieldTest):
    name = "Server"
    inputs = [b"Apache/2.4.1 (Unix)", b"CERN/3.0 libwww/2.17"]
    expected_out = ["Apache/2.4.1 (Unix)", "CERN/3.0 libwww/2.17"]
    expected_notes = []


class SERVER_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The Server header is long."
    _text = """\
The `Server` header is %(server_length)s long, which uses unnecessary bandwidth
and can expose details of the back-end system to attackers.

Consider shortening it."""


class ServerTooLongTest(FieldTest):
    name = "Server"
    inputs = [b"a" * (MAX_SERVER_LENGTH + 1)]
    expected_out = ["a" * (MAX_SERVER_LENGTH + 1)]
    expected_notes = [SERVER_TOO_LONG]
