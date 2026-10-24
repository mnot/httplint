from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    RequestLinterProtocol,
)


class from_field(SingletonField[RequestLinterProtocol]):
    canonical_name = "From"
    description = """\
The `From` header field contains an Internet email address for the human user who controls the
requesting user agent."""
    reference = f"{rfc9110.SPEC_URL}#field.from"
    syntax = rfc9110.From
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class FromTest(FieldTest[RequestLinterProtocol]):
    name = "From"
    inputs = [b"webmaster@example.org"]
    expected_out = "webmaster@example.org"


class FromQuotedTrailingSpaceTest(FieldTest[RequestLinterProtocol]):
    "quoted-string allows FWS before the closing quote (#303); this was BAD_SYNTAX."

    name = "From"
    inputs = [b'"Bob " <webmaster@example.org>']
    expected_out = '"Bob " <webmaster@example.org>'


class FromNestedCommentTest(FieldTest[RequestLinterProtocol]):
    "Comments nest (#303); this was BAD_SYNTAX_DETAILED."

    name = "From"
    inputs = [b"webmaster@example.org (Web (Master))"]
    expected_out = "webmaster@example.org (Web (Master))"
