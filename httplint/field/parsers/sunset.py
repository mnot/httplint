from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_http_date
from httplint.message import HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.field.utils import BAD_DATE_SYNTAX
from httplint.types import AddNoteMethodType


class sunset(SingletonField):
    canonical_name = "Sunset"
    description = """\
The `Sunset` header field indicates that the resource is likely to become unresponsive at the
specified timestamp."""
    reference = "https://www.rfc-editor.org/rfc/rfc8594.html"
    syntax = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(field_value, add_note, category=self.category)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.message.start_time and self.value and self.value < self.message.start_time:
            add_note(SUNSET_PAST)


class SUNSET_PAST(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The resource has Sunset."
    _text = """\
The `Sunset` header indicates that this resource has already passed its sunset date and may become
unresponsive."""


class SunsetTest(FieldTest):
    name = "Sunset"
    inputs = [b"Sat, 31 Dec 2022 23:59:59 GMT"]
    expected_out = 1672531199


class SunsetPastTest(FieldTest):
    name = "Sunset"
    inputs = [b"Sat, 01 Jan 2000 00:00:00 GMT"]
    expected_out = 946684800
    expected_notes = [SUNSET_PAST]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.start_time = 1000000000


class SunsetBadSyntaxTest(FieldTest):
    name = "Sunset"
    inputs = [b"not a date"]
    expected_out = None
    expected_notes = [BAD_DATE_SYNTAX]
