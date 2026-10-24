import re
from dataclasses import dataclass
from typing import Optional

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.params import split_params_off
from httplint.field.tests import FieldTest
from httplint.field.utils import RE_FLAGS, parse_params, parse_qvalue, syntax_position
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
)

# A well-formed parameter, followed by a ";" or the end of the value. The leading whitespace is
# left out of the match so that a failed match stays linear.
EXTRA_PARAM_RE = re.compile(
    rf";{rfc9110.OWS}({rfc9110.token})={rfc9110.parameter_value}(?={rfc9110.OWS}(?:;|\Z))",
    RE_FLAGS,
)


@dataclass
class AcceptLanguageValue:
    language: str
    q: Optional[float]  # pylint: disable=invalid-name  # RFC 9110 q-value


class accept_language(HttpListField[RequestLinterProtocol]):
    canonical_name = "Accept-Language"
    description = """\
The `Accept-Language` header field can be used by user agents to indicate the set of natural languages that are
preferred in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-language"
    syntax = rfc9110.Accept_Language
    category = categories.CONNEG
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> AcceptLanguageValue:
        language, param_str = split_params_off(field_value)
        language = language.lower()
        param_dict = parse_params(param_str, add_note, ["q"], delim=";")

        # An invalid q-value fails the field's syntax check, which has already reported it.
        q_val = parse_qvalue(param_dict, None, param_str)

        if param_dict:
            # RFC 9110 only defines q parameter for Accept-Language
            add_note(
                ACCEPT_LANGUAGE_BAD_SYNTAX,
                ref_uri=self.reference,
                position=syntax_position(self, field_value),
            )
            # That note covers the value's syntax defect only if nothing else is wrong: the
            # value has to match the syntax once its well-formed non-q parameters are removed.
            rest = EXTRA_PARAM_RE.sub(
                lambda match: match.group() if match.group(1).lower() == "q" else "", field_value
            )
            if self.matches_syntax(rest):
                self.suppress_syntax_note()

        return AcceptLanguageValue(language, q_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class ACCEPT_LANGUAGE_BAD_SYNTAX(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The Accept-Language header isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information.%(position)s"""


class AcceptLanguageTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"da, en-gb;q=0.8, en;q=0.7"]
    expected_out = [
        AcceptLanguageValue("da", None),
        AcceptLanguageValue("en-gb", 0.8),
        AcceptLanguageValue("en", 0.7),
    ]


class AcceptLanguageParamTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"en; foo=bar"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes: NoteClassListType = [ACCEPT_LANGUAGE_BAD_SYNTAX]


class AcceptLanguageBadQTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"en; q=abc"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes: NoteClassListType = [BAD_SYNTAX]  # one note: the syntax check reports it


class AcceptLanguageBadQSignTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"en; q=+1"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class AcceptLanguageBadQQuotedTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b'en; q="0.5"']
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class AcceptLanguageBadQRangeTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"en; q=1.5"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class AcceptLanguageQTrailingDotTest(FieldTest[RequestLinterProtocol]):
    name = "Accept-Language"
    inputs = [b"en; q=1., fr; q=0.123"]
    expected_out = [AcceptLanguageValue("en", 1.0), AcceptLanguageValue("fr", 0.123)]
    expected_notes: NoteClassListType = []
