from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
)


class content_language(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Language"
    description = """\
The `Content-Language` header describes the natural language(s) of the intended audience for the
messsage. Note that this might not convey all of the languages used."""
    reference = f"{rfc9110.SPEC_URL}#field.content-language"
    syntax = rfc9110.Content_Language
    category = categories.CONNEG
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.value:
            if len(self.value) != len(set(self.value)):
                seen = set()
                duplicates = set()
                for lang in self.value:
                    if lang in seen:
                        duplicates.add(lang)
                    seen.add(lang)
                for lang in duplicates:
                    add_note(CONTENT_LANGUAGE_DUP, lang=lang)


class CONTENT_LANGUAGE_DUP(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The %(lang)s language tag appears more than once."
    _text = """\
The `%(lang)s` language tag is used more than once in the `Content-Language` header.

Recipients will likely ignore duplicates."""


class ContentLanguageTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Language"
    inputs = [b"en-US"]
    expected_out = ["en-us"]


class ContentLanguageListTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Language"
    inputs = [b"en-US, fr"]
    expected_out = ["en-us", "fr"]


class ContentLanguageDupTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Language"
    inputs = [b"en-US, en-US"]
    expected_out = ["en-us", "en-us"]
    expected_notes: NoteClassListType = [CONTENT_LANGUAGE_DUP]


class ContentLanguageExtendedTest(FieldTest[AnyMessageLinterProtocol]):
    "Variant, extension and private-use subtags (the issue #238 reproduction)."

    name = "Content-Language"
    inputs = [b"en-x-foo, de-CH-1996, sl-rozaj, en-u-ca-gregory, zh-Hant-x-private, x-foo"]
    expected_out = [
        "en-x-foo",
        "de-ch-1996",
        "sl-rozaj",
        "en-u-ca-gregory",
        "zh-hant-x-private",
        "x-foo",
    ]


class ContentLanguageBracesTest(FieldTest[AnyMessageLinterProtocol]):
    "The literal text of the unexpanded template isn't a language tag."

    name = "Content-Language"
    inputs = [b"x-{ALPHA}"]
    expected_out = ["x-{alpha}"]
    expected_notes: NoteClassListType = [BAD_SYNTAX]
