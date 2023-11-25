from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7230
from httplint.types import AddNoteMethodType
from httplint.field.notes import BAD_SYNTAX


class content_length(HttpField):
    canonical_name = "Content-Length"
    description = """\
The `Content-Length` header indicates the size of the content, in number of bytes. In responses to
the HEAD method, it indicates the size of the content that would have been sent had the request
been a GET.

If Content-Length is incorrect, HTTP/1.1 persistent connections will not work, and caches may not
store the response (since they can't be sure if they have the whole response)."""
    reference = f"{rfc7230.SPEC_URL}#header.content_length"
    syntax = rfc7230.Content_Length
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return int(field_value)


class ContentLengthTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1"]
    expected_out = 1


class ContentLengthTextTest(FieldTest):
    name = "Content-Length"
    inputs = [b"a"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]


class ContentLengthSemiTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1;"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]


class ContentLengthSpaceTest(FieldTest):
    name = "Content-Length"
    inputs = [b" 1 "]
    expected_out = 1


class ContentLengthBigTest(FieldTest):
    name = "Content-Length"
    inputs = [b"9" * 999]
    expected_out = int("9" * 999)
