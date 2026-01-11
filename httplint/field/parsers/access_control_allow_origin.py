from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.note import Note, levels, categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class access_control_allow_origin(SingletonField):
    canonical_name = "Access-Control-Allow-Origin"
    description = """\
The `Access-Control-Allow-Origin` response header indicates whether the response can be shared with
requesting code from the given origin."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-origin"
    syntax = rf"(?:\*|null|{rfc9110.URI_reference})"
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if " " in field_value or "," in field_value:
            add_note(ACAO_MULTIPLE_VALUES)
        return field_value


class ACAO_MULTIPLE_VALUES(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "Access-Control-Allow-Origin should not have multiple values."
    _text = """\
The `Access-Control-Allow-Origin` header can only contain a single origin, `*`, or `null`. It
cannot contain a list of origins."""


class AccessControlAllowOriginTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"https://developer.mozilla.org"]
    expected_out = "https://developer.mozilla.org"

    def test_multiple(self) -> None:
        self.inputs = [b"https://foo.com, https://bar.com"]
        self.expected_notes = [ACAO_MULTIPLE_VALUES, BAD_SYNTAX]
        self.expected_out = "https://foo.com, https://bar.com"
        self.setUp()
        self.test_header()


class AccessControlAllowOriginStarTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"*"]
    expected_out = "*"


class AccessControlAllowOriginNullTest(FieldTest):
    name = "Access-Control-Allow-Origin"
    inputs = [b"null"]
    expected_out = "null"
