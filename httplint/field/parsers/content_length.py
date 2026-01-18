from typing import TYPE_CHECKING

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.field.singleton_field import SINGLE_HEADER_REPEAT
from httplint.note import Note, categories, levels

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class content_length(SingletonField):
    canonical_name = "Content-Length"
    description = """\
The `Content-Length` header indicates the size of the content, in number of bytes. In responses to
the HEAD method, it indicates the size of the content that would have been sent had the request
been a GET.

If Content-Length is incorrect, HTTP/1.1 persistent connections will not work, and caches may not
store the response (since they can't be sure if they have the whole response)."""
    reference = f"{rfc9110.SPEC_URL}#field.content-length"
    syntax = rfc9110.Content_Length
    report_syntax = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        try:
            value = int(field_value)
        except ValueError:
            add_note(CL_BAD_SYNTAX)
            raise
        if value > 9223372036854775807:  # 2^63-1
            add_note(CL_TOO_LARGE)
        return value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "transfer-encoding" in self.message.headers.parsed:
            add_note(CL_AND_TE_PRESENT)


class CL_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Content-Length should be an integer."
    _text = """\
The `Content-Length` header should be an integer, but it was not."""


class CL_AND_TE_PRESENT(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Content-Length and Transfer-Encoding should not be present together."
    _text = """\
RFC 9110 Section 8.6:
> A sender MUST NOT send a Content-Length header field in any message that contains a Transfer-Encoding header field.

This is because `Transfer-Encoding` overrides `Content-Length`."""


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
    expected_notes = [CL_BAD_SYNTAX]


class ContentLengthSemiTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1;"]
    expected_out = None
    expected_notes = [CL_BAD_SYNTAX]


class ContentLengthSpaceTest(FieldTest):
    name = "Content-Length"
    inputs = [b" 1 "]
    expected_out = 1


class ContentLengthBigTest(FieldTest):
    name = "Content-Length"
    inputs = [b"9" * 999]
    expected_out = int("9" * 999)
    expected_notes = [CL_TOO_LARGE]


class ContentLengthDuplicateTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1", b"1"]
    expected_out = 1
    expected_notes = [SINGLE_HEADER_REPEAT]


class ContentLengthCommaTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1, 1"]
    expected_out = None
    expected_notes = [CL_BAD_SYNTAX]


class ContentLengthDiffTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1", b"2"]
    expected_out = 1
    expected_notes = [SINGLE_HEADER_REPEAT]


class ContentLengthDiffCommaTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1, 2"]
    expected_out = None
    expected_notes = [CL_BAD_SYNTAX]


class ContentLengthTEPresentTest(FieldTest):
    name = "Content-Length"
    inputs = [b"1"]
    expected_out = 1
    expected_notes = [CL_AND_TE_PRESENT]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.headers.parsed["transfer-encoding"] = "chunked"
