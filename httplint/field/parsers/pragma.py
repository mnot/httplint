from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7234
from httplint.types import AddNoteMethodType
from httplint.field.notes import FIELD_DEPRECATED


class pragma(HttpField):
    canonical_name = "Pragma"
    description = """\
The `Pragma` header is used to include implementation-specific directives that might apply to any
recipient along the request chain.

This header is deprecated, in favour of `Cache-Control`."""
    reference = f"{rfc7234.SPEC_URL}#header.pragma"
    syntax = rfc7234.Pragma
    list_header = True
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "no-cache" in self.value:
            add_note(PRAGMA_NO_CACHE)
        others = [True for v in self.value if v != "no-cache"]
        if others:
            add_note(PRAGMA_OTHER)


class PRAGMA_NO_CACHE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Pragma: no-cache is a request directive, not a response directive."
    _text = """\
`Pragma` is a very old request header that is sometimes used as a response header, even though
this is not specified behaviour. `Cache-Control: no-cache` is more appropriate."""


class PRAGMA_OTHER(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = """The Pragma header is being used in an undefined way."""
    _text = """HTTP only defines `Pragma: no-cache`; other uses of this header are deprecated."""


class PragmaTest(FieldTest):
    name = "Pragma"
    inputs = [b"no-cache"]
    expected_out = ["no-cache"]
    expected_notes = [PRAGMA_NO_CACHE, FIELD_DEPRECATED]
