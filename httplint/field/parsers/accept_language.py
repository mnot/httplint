from dataclasses import dataclass
from typing import Optional

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.field.utils import parse_params
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels


@dataclass
class AcceptLanguageValue:
    language: str
    q: Optional[float]


class accept_language(HttpField):
    canonical_name = "Accept-Language"
    description = """\
The `Accept-Language` header field can be used by user agents to indicate the set of natural languages that are
preferred in the response."""
    reference = f"{rfc9110.SPEC_URL}#field.accept-language"
    syntax = rfc9110.Accept_Language
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> AcceptLanguageValue:
        try:
            language, param_str = field_value.split(";", 1)
        except ValueError:
            language, param_str = field_value, ""

        language = language.lower()
        param_dict = parse_params(param_str, add_note, ["q"], delim=";")

        q_val: Optional[float] = None
        if "q" in param_dict:
            q_str = param_dict.pop("q")
            try:
                if q_str is None:
                    raise ValueError
                if len(q_str) > 5:
                    raise ValueError
                q_val = float(q_str)
                if not 0.0 <= q_val <= 1.0:
                    raise ValueError
            except (ValueError, TypeError):
                add_note(BAD_Q_VALUE, language=language)
                q_val = None

        if param_dict:
            # RFC 9110 only defines q parameter for Accept-Language
            add_note(ACCEPT_LANGUAGE_BAD_SYNTAX, ref_uri=self.reference)

        return AcceptLanguageValue(language, q_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class BAD_Q_VALUE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The q value on '{language}' is invalid."
    _text = """\
The `q` parameter must be a decimal number between 0 and 1, with at most 3 digits of precision."""


class ACCEPT_LANGUAGE_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Accept-Language header isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""


class AcceptLanguageTest(FieldTest):
    name = "Accept-Language"
    inputs = [b"da, en-gb;q=0.8, en;q=0.7"]
    expected_out = [
        AcceptLanguageValue("da", None),
        AcceptLanguageValue("en-gb", 0.8),
        AcceptLanguageValue("en", 0.7),
    ]


class AcceptLanguageParamTest(FieldTest):
    name = "Accept-Language"
    inputs = [b"en; foo=bar"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes = [ACCEPT_LANGUAGE_BAD_SYNTAX, BAD_SYNTAX]


class AcceptLanguageBadQTest(FieldTest):
    name = "Accept-Language"
    inputs = [b"en; q=abc"]
    expected_out = [AcceptLanguageValue("en", None)]
    expected_notes = [BAD_Q_VALUE, BAD_SYNTAX]
