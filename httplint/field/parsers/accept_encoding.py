from typing import Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params


class accept_encoding(HttpField):
    canonical_name = "Accept-Encoding"
    description = """\
The `Accept-Encoding` header field can be used by user agents to indicate what response content-codings are
acceptable in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-encoding"
    syntax = rfc9110.Accept_Encoding
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

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

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AcceptEncodingTest(FieldTest):
    name = "Accept-Encoding"
    inputs = [b"gzip, identity; q=0.5, *;q=0"]
    expected_out = [
        ("gzip", {}),
        ("identity", {"q": "0.5"}),
        ("*", {"q": "0"}),
    ]
