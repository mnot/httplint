from dataclasses import dataclass
from typing import Optional

from httplint.field.conneg import BAD_Q_VALUE, parse_qvalue
from httplint.field.list_field import HttpListField
from httplint.field.media_type import parse_media_type_once
from httplint.field.params import split_params_off
from httplint.field.tests import FieldTest
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
        media_type, param_dict = parse_media_type_once(
            self,
            field_value,
            add_note,
            ACCEPT_BAD_SYNTAX,
            allow_wildcard=True,
            nostar=["q"],
        )

        _, raw_params = split_params_off(field_value)
        q_val = parse_qvalue(param_dict, add_note, raw_params, item=media_type)

        return AcceptValue(media_type, param_dict, q_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ACCEPT_BAD_SYNTAX(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The Accept header contains a value that is not a media range."
    _text = """\
`%(value)s` is not a valid media range. `Accept` is a list of media ranges
(e.g., `text/html`, `image/*`, `*/*`) that the client prefers in the response;
see [its definition](%(ref_uri)s) for more information.%(position)s"""


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
    expected_notes: NoteClassListType = [ACCEPT_BAD_SYNTAX]


class AcceptBadQSignTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"text/html; q=+1"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptBadQExponentTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"text/html; q=1e0"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptBadQNoLeadingDigitTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b"text/html; q=.5"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptBadQQuotedTest(FieldTest[RequestLinterProtocol]):
    name = "Accept"
    inputs = [b'text/html; q="0.5"']
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptBadQTooPreciseTest(FieldTest[RequestLinterProtocol]):
    "Guard: main also rejects this."

    name = "Accept"
    inputs = [b"text/html; q=0.1234"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes: NoteClassListType = [BAD_Q_VALUE]


class AcceptQTrailingDotTest(FieldTest[RequestLinterProtocol]):
    "Guard: rfc9110.qvalue allows a bare '.' after the digit, as main does."

    name = "Accept"
    inputs = [b"text/html; q=1., text/plain; q=0., text/css; q=0.123, text/csv; q=1.000"]
    expected_out = [
        AcceptValue("text/html", {}, 1.0),
        AcceptValue("text/plain", {}, 0.0),
        AcceptValue("text/css", {}, 0.123),
        AcceptValue("text/csv", {}, 1.0),
    ]
    expected_notes: NoteClassListType = []


class AcceptSpaceBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "Guard: OWS before the ';' (media-range parameters and weight) was already stripped on main."

    name = "Accept"
    inputs = [b"text/html ; level=1 ; q=0.5, text/plain\t;\tq=0.1"]
    expected_out = [
        AcceptValue("text/html", {"level": "1"}, 0.5),
        AcceptValue("text/plain", {}, 0.1),
    ]
    expected_notes: NoteClassListType = []


class AcceptNoSpaceBeforeSemicolonTest(FieldTest[RequestLinterProtocol]):
    "Guard: no whitespace before the ';' (same on main)."

    name = "Accept"
    inputs = [b"text/html;q=0.5"]
    expected_out = [AcceptValue("text/html", {}, 0.5)]
    expected_notes: NoteClassListType = []
