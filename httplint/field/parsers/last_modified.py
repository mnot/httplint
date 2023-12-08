from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7232
from httplint.types import AddNoteMethodType
from httplint.util import relative_time
from httplint.field.notes import Note, categories, levels, BAD_DATE_SYNTAX
from httplint.field.utils import parse_http_date


class last_modified(HttpField):
    canonical_name = "Last-Modified"
    description = """\
The `Last-Modified` response header indicates the time that the origin server believes the
representation was last modified."""
    reference = f"{rfc7232.SPEC_URL}#header.last_modified"
    syntax = False  # rfc7232.Last_Modified
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(field_value, add_note)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        date_value = self.message.headers.parsed.get("date", None)
        lm_value = self.value
        if lm_value:
            serv_date = date_value or self.message.start_time
            if not serv_date:
                return  # we don't know
            if lm_value > serv_date:
                add_note(LM_FUTURE)
            else:
                add_note(
                    LM_PRESENT,
                    last_modified_string=relative_time(lm_value, serv_date),
                )


class LM_FUTURE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Last-Modified time is in the future."
    _text = """\
The `Last-Modified` header indicates the last point in time that the resource has changed.
%(message)s's `Last-Modified` time is in the future, which doesn't have any defined meaning in
HTTP."""


class LM_PRESENT(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource last changed %(last_modified_string)s."
    _text = """\
The `Last-Modified` header indicates the last point in time that the resource has changed. It is
used in HTTP for validating cached responses, and for calculating heuristic freshness in caches.

This resource last changed %(last_modified_string)s."""


class BasicLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b"0"]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]


class BlankLMTest(FieldTest):
    name = "Last-Modified"
    inputs = [b""]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]
