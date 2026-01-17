from dataclasses import dataclass
from typing import Optional

from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.field.utils import parse_params
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.note import Note, categories, levels


@dataclass
class AcceptValue:
    media_type: str
    parameters: ParamDictType
    q: Optional[float]


class accept(HttpListField):
    canonical_name = "Accept"
    description = """\
The `Accept` header field can be used by user agents to specify response media types that are
acceptable in responses."""
    reference = f"{rfc9110.SPEC_URL}#field.accept"
    syntax = rfc9110.Accept
    category = categories.CONNEG
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> AcceptValue:
        try:
            media_type, param_str = field_value.split(";", 1)
        except ValueError:
            media_type, param_str = field_value, ""

        media_type = media_type.lower()
        # check media type syntax?
        # rfc9110.media_range is ( "*/*" / ( type "/*" ) / ( type "/" subtype ) )
        # We assume regex pre-check might handle some, but simple split is safer.
        if "/" not in media_type and media_type != "*":
            add_note(ACCEPT_BAD_SYNTAX, ref_uri=self.reference)

        param_dict = parse_params(param_str, add_note, ["q"], delim=";")

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
    _summary = "The Accept header isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""


class AcceptTest(FieldTest):
    name = "Accept"
    inputs = [b"audio/*; q=0.2, audio/basic"]
    expected_out = [
        AcceptValue("audio/*", {}, 0.2),
        AcceptValue("audio/basic", {}, None),
    ]


class AcceptComplexTest(FieldTest):
    name = "Accept"
    inputs = [b"text/html; level=1; q=0.5"]
    expected_out = [AcceptValue("text/html", {"level": "1"}, 0.5)]


class AcceptBadQTest(FieldTest):
    name = "Accept"
    inputs = [b"text/html; q=1.001"]
    expected_out = [AcceptValue("text/html", {}, None)]
    expected_notes = [BAD_Q_VALUE]


class AcceptBadTypeTest(FieldTest):
    name = "Accept"
    inputs = [b"invalid"]
    expected_out = [AcceptValue("invalid", {}, None)]
    expected_notes = [ACCEPT_BAD_SYNTAX, BAD_SYNTAX]
