from typing import Tuple

from httplint.fields import HttpField
from httplint.fields._test import FieldTest
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.fields._utils import parse_params


class content_type(HttpField):
    canonical_name = "Content-Type"
    description = """\
The `Content-Type` header indicates the media type of the content sent to the recipient or, in the
case of responses to the HEAD method, the media type that would have been sent had the request been
a GET."""
    reference = f"{rfc7231.SPEC_URL}#header.content_type"
    syntax = rfc7231.Content_Type
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        try:
            media_type, param_str = field_value.split(";", 1)
        except ValueError:
            media_type, param_str = field_value, ""
        media_type = media_type.lower()
        param_dict = parse_params(param_str, add_note, ["charset"])
        return media_type, param_dict


class BasicCTTest(FieldTest):
    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-8"]
    expected_out = ("text/plain", {"charset": "utf-8"})
