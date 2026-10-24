from httplint.field.date_field import HttpDateField
from httplint.field.http_date import BAD_DATE_SYNTAX
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, NoteClassListType, ResponseLinterProtocol


class sunset(HttpDateField[ResponseLinterProtocol]):
    canonical_name = "Sunset"
    description = """\
The `Sunset` header field indicates that the resource is likely to become unresponsive at the
specified timestamp."""
    reference = "https://www.rfc-editor.org/rfc/rfc8594.html"
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.message.start_time is not None and self.value < self.message.start_time:
            add_note(SUNSET_PAST)


class SUNSET_PAST(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The resource has Sunset."
    _text = """\
The `Sunset` header indicates that this resource has already passed its sunset date and may become
unresponsive."""


class SunsetTest(FieldTest[ResponseLinterProtocol]):
    name = "Sunset"
    inputs = [b"Sat, 31 Dec 2022 23:59:59 GMT"]
    expected_out = 1672531199


class SunsetPastTest(FieldTest[ResponseLinterProtocol]):
    name = "Sunset"
    inputs = [b"Sat, 01 Jan 2000 00:00:00 GMT"]
    expected_out = 946684800
    expected_notes: NoteClassListType = [SUNSET_PAST]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 1000000000


class SunsetBadSyntaxTest(FieldTest[ResponseLinterProtocol]):
    name = "Sunset"
    inputs = [b"not a date"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class SunsetEpochTest(FieldTest[ResponseLinterProtocol]):
    name = "Sunset"
    inputs = [b"Thu, 01 Jan 1970 00:00:00 GMT"]
    expected_out = 0
    expected_notes: NoteClassListType = [SUNSET_PAST]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 1000000000


class SunsetYearZeroTest(FieldTest[ResponseLinterProtocol]):
    name = "Sunset"
    inputs = [b"Mon, 01 Jan 0000 00:00:00 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]
