from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9111
from httplint.types import AddNoteMethodType
from httplint.field import FIELD_DEPRECATED


class pragma(HttpField):
    canonical_name = "Pragma"
    description = """\
The `Pragma` header is used to include implementation-specific directives that might apply to any
recipient along the request chain.

This header is deprecated, in favour of `Cache-Control`."""
    reference = f"{rfc9111.SPEC_URL}#field.pragma"
    syntax = rfc9111.Pragma
    category = categories.CACHING
    deprecated = True
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        others = [True for v in self.value if v != "no-cache"]
        if others:
            add_note(PRAGMA_OTHER)


class PRAGMA_OTHER(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = """The Pragma header is being used in an undefined way."""
    _text = """HTTP only defines `Pragma: no-cache`; other uses of this header are deprecated."""


class PragmaTest(FieldTest):
    name = "Pragma"
    inputs = [b"no-cache"]
    expected_out = ["no-cache"]
    expected_notes = [FIELD_DEPRECATED]
