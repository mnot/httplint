from typing import Any, Tuple

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import (
    MEDIA_TYPE_BAD_NAME,
    MEDIA_TYPE_LONG_NAME,
    parse_media_type,
)
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
    ParamDictType,
)


class content_type(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Type"
    description = """\
The `Content-Type` header indicates the media type of the content sent to the recipient or, in the
case of responses to the HEAD method, the media type that would have been sent had the request been
a GET."""
    reference = f"{rfc9110.SPEC_URL}#field.content-type"
    syntax = rfc9110.Content_Type
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        return parse_media_type(field_value, add_note, nostar=["charset"])


class BasicCTTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-8"]
    expected_out = ("text/plain", {"charset": "utf-8"})


class CTSuffixTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"application/vnd.example.foo-bar+json"]
    expected_out: Any = ("application/vnd.example.foo-bar+json", {})


class CTBadNameTest(FieldTest[AnyMessageLinterProtocol]):
    "A media type that's a valid HTTP token, but not a valid RFC 6838 name."

    name = "Content-Type"
    inputs = [b"text/pl~in"]
    expected_out: Any = ("text/pl~in", {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_BAD_NAME]


class CTBadNameFirstTest(FieldTest[AnyMessageLinterProtocol]):
    "RFC 6838 names have to start with a letter or a digit."

    name = "Content-Type"
    inputs = [b"text/.plain"]
    expected_out: Any = ("text/.plain", {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_BAD_NAME]


class CTLongNameTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/" + b"a" * 128]
    expected_out: Any = ("text/" + "a" * 128, {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_LONG_NAME]
