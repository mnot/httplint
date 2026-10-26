from typing import Tuple

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.params import parse_params, split_params_off
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
    ParamDictType,
)


class te(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "TE"
    description = """\
The `TE` request header indicates what HTTP/1.1 transfer-codings the client is willing to accept in
the response. Additionally, if it contains the special value `trailers` it indicates that the sender is willing to accept trailer fields after the content.

The most common transfer-coding, `chunked`, doesn't need to be listed in `TE`.

`TE` can only be used with the value `trailers` in HTTP/2 and HTTP/3.
"""
    reference = f"{rfc9110.SPEC_URL}#field.te"
    syntax = rfc9110.TE
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        encoding, param_str = split_params_off(field_value)
        encoding = encoding.lower()
        param_dict = parse_params(param_str, add_note, ["q"], delim=";")
        return encoding, param_dict


class TETest(FieldTest[AnyMessageLinterProtocol]):
    name = "TE"
    inputs = [b"trailers, deflate; q=0.5"]
    expected_out = [("trailers", {}), ("deflate", {"q": "0.5"})]


class TEQuotedSemicolonTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: the head is split off at the first ';' even inside quotes; it's invalid either way."

    name = "TE"
    inputs = [b'"a;b"']
    expected_out = [('"a', {})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class TENoWhitespaceBeforeSemicolonTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: no whitespace before ';'."

    name = "TE"
    inputs = [b"gzip;q=0.5"]
    expected_out = [("gzip", {"q": "0.5"})]


class TESpaceBeforeSemicolonTest(FieldTest[AnyMessageLinterProtocol]):
    "OWS is allowed before ';' and isn't part of the coding."

    name = "TE"
    inputs = [b"gzip ;q=0.5"]
    expected_out = [("gzip", {"q": "0.5"})]


class TETabBeforeSemicolonTest(FieldTest[AnyMessageLinterProtocol]):
    "A tab (OWS) is allowed before ';' and isn't part of the coding."

    name = "TE"
    inputs = [b"gzip\t;q=0.5"]
    expected_out = [("gzip", {"q": "0.5"})]
