from typing import Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params


class te(HttpField):
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
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        try:
            encoding, param_str = field_value.split(";", 1)
        except ValueError:
            encoding, param_str = field_value, ""
        encoding = encoding.lower()
        param_dict = parse_params(param_str, add_note, ["q"], delim=";")
        return encoding, param_dict


class TETest(FieldTest):
    name = "TE"
    inputs = [b"trailers, deflate; q=0.5"]
    expected_out = [("trailers", {}), ("deflate", {"q": "0.5"})]
