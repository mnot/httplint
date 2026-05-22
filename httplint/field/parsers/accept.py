from dataclasses import dataclass
from typing import Optional

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_media_type
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ParamDictType,
    RequestLinterProtocol,
)


@dataclass
class AcceptValue:
    media_type: str
    parameters: ParamDictType
    q: Optional[float]  # pylint: disable=invalid-name  # RFC 9110 q-value


class accept(HttpListField[RequestLinterProtocol]):
    canonical_name = "Accept"
    description = """\
The `Accept` header field can be used by user agents to specify response media types that are
acceptable in responses."""
    reference = f"{rfc9110.SPEC_URL}#field.accept"
    syntax = rfc9110.Accept
    category = categories.CONNEG
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> AcceptValue:
        media_type, param_dict = parse_media_type(
            field_value,
            add_note,
            ACCEPT_BAD_SYNTAX,
            self.reference,
            allow_wildcard=True,
            nostar=["q"],
        )

        q_val: Optional[float] = None
        if "q" in param_dict:
            try:
                q_str = param_dict.pop("q")
                if q_str is None:
                    raise ValueError
                if len(q_str) > 5:  # 0.123
                    raise ValueError
                q_val = float(q_str)
                if not 0.0 <= q_val <= 1.0:
                    raise ValueError
            except (ValueError, TypeError):
                add_note(BAD_Q_VALUE, media_type=media_type)
                q_val = None  # Discard invalid q

        return AcceptValue(media_type, param_dict, q_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class BAD_Q_VALUE(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "The q value on '{media_type}' is invalid."
    _text = """\
The `q` parameter must be a decimal number between 0 and 1, with at most 3 digits of precision."""


class ACCEPT_BAD_SYNTAX(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The Accept header contains a value that is not a media range."
    _text = """\
`%(value)s` is not a valid media range. `Accept` is a list of media ranges
(e.g., `text/html`, `image/*`, `*/*`) that the client prefers in the response;
see [its definition](%(ref_uri)s) for more information."""


class AcceptTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"audio/*; q=0.2, audio/basic"]
    expected_out = [
        AcceptValue("audio/*", {}, 0.2),
        AcceptValue("audio/basic", {}, None),
    ]


class AcceptComplexTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"text/html; level=1; q=0.5"]
    expected_out = [AcceptValue("text/html", {"level": "1"}, 0.5)]


class AcceptBadQTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"text/html; q=1.001"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptBadTypeTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"invalid"]
    expected_out = [AcceptValue("invalid", {}, None)]
    expected_notes: NoteClassListType = [ACCEPT_BAD_SYNTAX, BAD_SYNTAX]
