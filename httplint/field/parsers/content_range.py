from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter, HttpResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class content_range(SingletonField):
    canonical_name = "Content-Range"
    description = """\
The `Content-Range` response header is sent in a `206` (Partial Content) response to indicate
where in the full response content the partial content is located. It is also used
in `416` (Requested Range Not Satisfiable) responses."""
    reference = f"{rfc9110.SPEC_URL}#field.content-range"
    syntax = rfc9110.Content_Range
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        # #53: check syntax, values?
        if isinstance(
            self.message, HttpResponseLinter
        ) and self.message.status_code not in [
            206,
            416,
        ]:
            add_note(CONTENT_RANGE_MEANINGLESS)
        return field_value


class CONTENT_RANGE_MEANINGLESS(Note):
    category = categories.RANGE
    level = levels.WARN
    _summary = "This response shouldn't have a Content-Range header."
    _text = """\
HTTP only defines meaning for the `Content-Range` header in responses with a `206` (Partial
Content) or `416` (Requested Range Not Satisfiable) status code.

Because the status code is neither of those, this `Content-Range` header may confuse caches and
clients."""


class ContentRangeTest(FieldTest):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200"]
    expected_out = "bytes 1-100/200"

    def set_context(self, message: HttpMessageLinter) -> None:
        message.status_code = 206  # type: ignore
