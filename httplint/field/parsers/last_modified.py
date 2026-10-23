from httplint.field.date_field import HttpDateField
from httplint.field.tests import FieldTest
from httplint.field.utils import BAD_DATE_SYNTAX
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)
from httplint.util import relative_time


class last_modified(HttpDateField[ResponseLinterProtocol]):
    canonical_name = "Last-Modified"
    description = """\
The `Last-Modified` response header indicates the time that the origin server believes the
representation was last modified."""
    reference = f"{rfc9110.SPEC_URL}#field.last-modified"
    category = categories.CACHING
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        date_value = self.message.headers.parsed.get("date", None)
        lm_value = self.value
        if lm_value is not None:
            serv_date = date_value if date_value is not None else self.message.start_time
            if serv_date is None:
                return  # cannot determine relative time without a server timestamp
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
This response's `Last-Modified` time is in the future, which doesn't have any defined meaning in
HTTP."""


class LM_PRESENT(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource last changed %(last_modified_string)s."
    _text = """\
The `Last-Modified` header indicates the last point in time that the resource has changed. It is
used in HTTP for validating cached responses, and for calculating heuristic freshness in caches.

This resource last changed %(last_modified_string)s."""


class BasicLMTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadLMTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b"0"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class LMLowerCaseTest(FieldTest[ResponseLinterProtocol]):
    "The day name, month and GMT are case-sensitive."

    name = "Last-Modified"
    inputs = [b"mon, 04 jul 2011 09:08:06 gmt"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class BlankLMTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b""]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class LMEpochTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b"Thu, 01 Jan 1970 00:00:00 GMT"]
    expected_out = 0
    expected_notes: NoteClassListType = [LM_PRESENT]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 1_000_000_000.0


class LMEpochDateTest(FieldTest[ResponseLinterProtocol]):
    "An epoch Date is the server's time, not something to fall back from."

    name = "Last-Modified"
    inputs = [b"Fri, 02 Jan 1970 00:00:00 GMT"]
    expected_out = 86400
    expected_notes: NoteClassListType = [LM_FUTURE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 1_000_000_000.0
        message.headers.parsed["date"] = 0


class LMYearZeroTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b"Mon, 01 Jan 0000 00:00:00 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class LMImpossibleTest(FieldTest[ResponseLinterProtocol]):
    name = "Last-Modified"
    inputs = [b"Mon, 31 Feb 2011 25:61:61 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]
