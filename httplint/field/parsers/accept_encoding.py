from typing import Tuple

from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.codings import CODING_ALIAS_DEPRECATED, note_deprecated_codings
from httplint.field.list_field import HttpListField
from httplint.field.params import parse_params, split_params_off
from httplint.field.section import FIELD_VALUE_ENCODING
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ParamDictType,
    RequestLinterProtocol,
)


class accept_encoding(HttpListField[RequestLinterProtocol]):
    canonical_name = "Accept-Encoding"
    description = """\
The `Accept-Encoding` header field can be used by user agents to indicate what response content-codings are
acceptable in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-encoding"
    syntax = rfc9110.Accept_Encoding
    category = categories.CONNEG
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        encoding, param_str = split_params_off(field_value)
        encoding = encoding.lower()
        param_dict = parse_params(param_str, add_note, ["q"], delim=";")
        return encoding, param_dict

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        note_deprecated_codings((coding for coding, _ in self.value), add_note, self.category)


class AcceptEncodingTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Encoding"
    inputs = [b"gzip, identity; q=0.5, *;q=0"]
    expected_out = [
        ("gzip", {}),
        ("identity", {"q": "0.5"}),
        ("*", {"q": "0"}),
    ]


class AcceptEncodingXGzipTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Encoding"
    inputs = [b"x-gzip"]
    expected_out = [("x-gzip", {})]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]


class AcceptEncodingXGzipQTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Encoding"
    inputs = [b"gzip, x-gzip;q=0.5"]
    expected_out = [("gzip", {}), ("x-gzip", {"q": "0.5"})]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]


class AcceptEncodingXCompressTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Encoding"
    inputs = [b"X-Compress"]
    expected_out = [("x-compress", {})]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]


class AcceptEncodingStandardCodingsTest(FieldTest[RequestLinterProtocol]):
    "Guard: gzip and compress don't get the deprecated-alias note."

    name = "Accept-Encoding"
    inputs = [b"gzip, compress;q=0.5"]
    expected_out = [("gzip", {}), ("compress", {"q": "0.5"})]
    expected_notes: NoteClassListType = []


class AcceptEncodingSpaceBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "OWS before the ';' is part of the weight, not of the coding (#330)."

    name = "Accept-Encoding"
    inputs = [b"gzip ; q=0.5, br ;q=0"]
    expected_out = [("gzip", {"q": "0.5"}), ("br", {"q": "0"})]
    expected_notes: NoteClassListType = []


class AcceptEncodingTabBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Encoding"
    inputs = [b"gzip\t;\tq=0.5"]
    expected_out = [("gzip", {"q": "0.5"})]
    expected_notes: NoteClassListType = []


class AcceptEncodingNoSpaceBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "Guard: no whitespace before the ';' (same on main)."

    name = "Accept-Encoding"
    inputs = [b"gzip;q=0.5"]
    expected_out = [("gzip", {"q": "0.5"})]
    expected_notes: NoteClassListType = []


class AcceptEncodingNonOWSBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "Guard: only SP and HTAB are stripped; a no-break space stays in the coding (same on main)."

    name = "Accept-Encoding"
    inputs = [b"gzip\xa0;q=0.5"]
    expected_out = [("gzip\xa0", {"q": "0.5"})]
    expected_notes: NoteClassListType = [FIELD_VALUE_ENCODING, BAD_SYNTAX_DETAILED]


class AcceptEncodingAliasSpaceBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "The deprecated alias is recognised with OWS before the ';' (it was missed on main)."

    name = "Accept-Encoding"
    inputs = [b"x-gzip ;q=0.5, * ;q=0"]
    expected_out = [("x-gzip", {"q": "0.5"}), ("*", {"q": "0"})]
    expected_notes: NoteClassListType = [CODING_ALIAS_DEPRECATED]
