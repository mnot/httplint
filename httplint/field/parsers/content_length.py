from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.field.notes import BAD_SYNTAX
from httplint.note import Note, categories, levels


class content_length(HttpField):
    canonical_name = "Content-Length"
    description = """\
The `Content-Length` header indicates the size of the content, in number of bytes. In responses to
the HEAD method, it indicates the size of the content that would have been sent had the request
been a GET.

If Content-Length is incorrect, HTTP/1.1 persistent connections will not work, and caches may not
store the response (since they can't be sure if they have the whole response)."""
    reference = f"{rfc9110.SPEC_URL}#field.content-length"
    syntax = rfc9110.Content_Length
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        value = int(field_value)
        if value > 9223372036854775807:  # 2^63-1
            add_note(CL_TOO_LARGE)
        return value


class CL_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Content-Length header is very large."
    _text = """\
The `Content-Length` header's value is greater than 2^63-1. Some implementations may not be able to
handle values this large."""


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
    expected_notes = [CL_TOO_LARGE]
