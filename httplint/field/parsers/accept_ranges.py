from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7233
from httplint.types import AddNoteMethodType


class accept_ranges(HttpField):
    canonical_name = "Accept-Ranges"
    description = """\
The `Accept-Ranges` response header allows the server to indicate that it accepts range requests
for a resource."""
    reference = f"{rfc7233.SPEC_URL}#header.accept-ranges"
    syntax = rfc7233.Accept_Ranges
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        field_value = field_value.lower()
        if field_value not in ["bytes", "none"]:
            add_note(UNKNOWN_RANGE, range=field_value)
        return field_value


class UNKNOWN_RANGE(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = "%(message)s advertises support for non-standard range-units."
    _text = """\
The `Accept-Ranges` response header tells clients what `range-unit`s a resource is willing to
process in future requests. HTTP only defines two: `bytes` and `none`.

Clients who don't know about the non-standard range-unit will not be able to use it."""


class AcceptRangeTest(FieldTest):
    name = "Accept-Ranges"
    inputs = [b"bytes"]
    expected_out = ["bytes"]


class NoneAcceptRangeTest(FieldTest):
    name = "Accept-Ranges"
    inputs = [b"none"]
    expected_out = ["none"]


class BothAcceptRangeTest(FieldTest):
    name = "Accept-Ranges"
    inputs = [b"bytes, none"]
    expected_out = ["bytes", "none"]


class BadAcceptRangeTest(FieldTest):
    name = "Accept-Ranges"
    inputs = [b"foo"]
    expected_out = ["foo"]
    expected_notes = [UNKNOWN_RANGE]


class CaseAcceptRangeTest(FieldTest):
    name = "Accept-Ranges"
    inputs = [b"Bytes, NONE"]
    expected_out = ["bytes", "none"]
