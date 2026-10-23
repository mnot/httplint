from dataclasses import dataclass
from typing import Any, Optional, Type

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import PARAM_REPEATS, parse_params, parse_qvalue
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
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
        try:
            language, param_str = field_value.split(";", 1)
        except ValueError:
            language, param_str = field_value, ""

        language = language.lower()
        q_repeated = False

        def track(note: Type[Note], category: Optional[Any] = None, **vrs: Any) -> Note:
            nonlocal q_repeated
            q_repeated = q_repeated or (note is PARAM_REPEATS and vrs.get("param") == "q")
            return add_note(note, category, **vrs)

        param_dict = parse_params(param_str, track, ["q"], delim=";")
        has_q = "q" in param_dict

        # An invalid q-value fails the field's syntax check, which has already reported it.
        q_val = parse_qvalue(param_dict, None, param_str)

        if param_dict:
            # RFC 9110 only defines q parameter for Accept-Language
            add_note(ACCEPT_LANGUAGE_BAD_SYNTAX, ref_uri=self.reference)
            # That note covers the value's syntax defect only if the language and the q-value
            # (if any) are fine: they would match with the other parameters removed.
            weight = f";q={q_val:.3f}" if q_val is not None else ""
            full, _ = self._syntax_patterns() or (None, None)  # pylint: disable=protected-access
            if (
                full is not None
                and (q_val is not None or not has_q)
                and not q_repeated
                and full.match(f"{language.strip()}{weight}")
            ):
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
definition](%(ref_uri)s) for more information."""


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
