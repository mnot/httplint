from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class content_language(HttpListField):
    canonical_name = "Content-Language"
    description = """\
The `Content-Language` header describes the natural language(s) of the intended audience for the
messsage. Note that this might not convey all of the languages used."""
    reference = f"{rfc9110.SPEC_URL}#field.content-language"
    syntax = rfc9110.Content_Language
    category = categories.CONNEG
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

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


class ContentLanguageTest(FieldTest):
    name = "Content-Language"
    inputs = [b"en-US"]
    expected_out = ["en-us"]


class ContentLanguageListTest(FieldTest):
    name = "Content-Language"
    inputs = [b"en-US, fr"]
    expected_out = ["en-us", "fr"]


class ContentLanguageDupTest(FieldTest):
    name = "Content-Language"
    inputs = [b"en-US, en-US"]
    expected_out = ["en-us", "en-us"]
    expected_notes = [CONTENT_LANGUAGE_DUP]
