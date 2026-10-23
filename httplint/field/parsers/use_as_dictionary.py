from typing import Any, List, Union

from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFDictionaryType,
)


class use_as_dictionary(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Use-As-Dictionary"
    description = """\
The `Use-As-Dictionary` header field is used by a server to indicate that the response can be used
as a compression dictionary for future requests."""
    reference = "https://www.rfc-editor.org/rfc/rfc9842.html"
    syntax = False  # Structured Field
    category = categories.CONNEG
    deprecated = False
    sf_type = "dictionary"
    value: SFDictionaryType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "match" not in self.value:
            add_note(USE_AS_DICTIONARY_NO_MATCH)
        for key, val in self.value.items():
            if key == "match":
                self._check_value_type(key, val, str, add_note)
            elif key == "match-dest":
                # Inner List of Strings: list of (value, params)
                if not (
                    isinstance(val[0], list)
                    and all(isinstance(i, tuple) and isinstance(i[0], str) for i in val[0])
                ):
                    add_note(USE_AS_DICTIONARY_BAD_MATCH_DEST, got=type(val[0]).__name__)
            elif key == "id":
                self._check_value_type(key, val, str, add_note)
            elif key == "type":
                self._check_value_type(key, val, Token, add_note)

    def _check_value_type(
        self,
        key: str,
        val: Union[tuple[Any, Any], List[Any]],
        expected_type: type,
        add_note: AddNoteMethodType,
    ) -> None:
        # val is (value, params) or list of (value, params) for Inner List
        # Dictionary values are Items or Inner Lists.
        # If expected type is simple (str, int), we assume it's an Item.
        if isinstance(val, list):
            # Inner List found where simple Item expected
            add_note(
                USE_AS_DICTIONARY_BAD_TYPE,
                param=key,
                expected=expected_type.__name__,
                got="Inner List",
            )
            return

        if not isinstance(val[0], expected_type):
            add_note(
                USE_AS_DICTIONARY_BAD_TYPE,
                param=key,
                expected=expected_type.__name__,
                got=type(val[0]).__name__,
            )


class USE_AS_DICTIONARY_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s parameter '%(param)s' has an invalid type."
    _text = """\
The `%(field_name)s` parameter `%(param)s` must be a `%(expected)s`. Found `%(got)s`."""


class USE_AS_DICTIONARY_BAD_MATCH_DEST(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The match-dest parameter has an invalid type."
    _text = """\
The `match-dest` parameter must be an Inner List of Strings."""


class USE_AS_DICTIONARY_NO_MATCH(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Use-As-Dictionary header does not have a match parameter."
    _text = """\
The `match` parameter MUST be included for the dictionary to be considered valid, so this
dictionary will not be used."""


class UseAsDictionaryTest(FieldTest[ResponseLinterProtocol]):
    name = "Use-As-Dictionary"
    inputs = [b'match="/foo/*", id="abc", type=raw, match-dest=("document" "frame")']
    expected_out = {
        "match": ("/foo/*", {}),
        "id": ("abc", {}),
        "type": (Token("raw"), {}),
        "match-dest": ([("document", {}), ("frame", {})], {}),
    }
    expected_notes: NoteClassListType = []


class UseAsDictionaryBadParamTest(FieldTest[ResponseLinterProtocol]):
    name = "Use-As-Dictionary"
    inputs = [b'match=123, id=456, type="raw"']
    expected_out = {"match": (123, {}), "id": (456, {}), "type": ("raw", {})}
    expected_notes: NoteClassListType = [
        USE_AS_DICTIONARY_BAD_TYPE,
        USE_AS_DICTIONARY_BAD_TYPE,
        USE_AS_DICTIONARY_BAD_TYPE,
    ]


class UseAsDictionaryBareMatchDestTest(FieldTest[ResponseLinterProtocol]):
    name = "Use-As-Dictionary"
    inputs = [b'match="/foo/*", match-dest="document"']
    expected_out = {"match": ("/foo/*", {}), "match-dest": ("document", {})}
    expected_notes: NoteClassListType = [USE_AS_DICTIONARY_BAD_MATCH_DEST]


class UseAsDictionaryNoMatchTest(FieldTest[ResponseLinterProtocol]):
    name = "Use-As-Dictionary"
    inputs = [b"id=\"abc\""]
    expected_out = {"id": ("abc", {})}
    expected_notes: NoteClassListType = [USE_AS_DICTIONARY_NO_MATCH]
