from typing import List, Union

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class use_as_dictionary(StructuredField):
    canonical_name = "Use-As-Dictionary"
    description = """\
The `Use-As-Dictionary` header field is used by a server to indicate that the response can be used
as a compression dictionary for future requests."""
    reference = "https://www.rfc-editor.org/rfc/rfc9842.html"
    syntax = False  # Structured Field
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "dictionary"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        for key, val in self.value.items():
            if key == "match":
                self._check_value_type(val, str, add_note)
            elif key == "match-dest":
                # Can be a String or Inner List of Strings
                is_valid = False
                if isinstance(val, tuple) and isinstance(val[0], str):
                    is_valid = True
                elif isinstance(val, list):
                    # Inner List: list of (value, params)
                    if all(isinstance(i[0], str) for i in val):
                        is_valid = True

                if not is_valid:
                    add_note(USE_AS_DICTIONARY_BAD_MATCH_DEST, got=type(val).__name__)

            elif key == "id":
                self._check_value_type(val, str, add_note)
            elif key == "type":
                self._check_value_type(val, str, add_note)
            elif key == "ttl":
                self._check_value_type(val, int, add_note)

    def _check_value_type(
        self,
        val: Union[tuple, List],
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
                param=val,
                expected=expected_type.__name__,
                got="Inner List",
            )
            return

        if not isinstance(val[0], expected_type):
            add_note(
                USE_AS_DICTIONARY_BAD_TYPE,
                param=val[0],
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
The `match-dest` parameter must be a String or a list of Strings."""


class UseAsDictionaryTest(FieldTest):
    name = "Use-As-Dictionary"
    inputs = [b'match="/foo/*", ttl=123']
    expected_out = {"match": ("/foo/*", {}), "ttl": (123, {})}
    expected_notes = []


class UseAsDictionaryBadParamTest(FieldTest):
    name = "Use-As-Dictionary"
    inputs = [b'match=123, ttl="abc"']
    expected_out = {"match": (123, {}), "ttl": ("abc", {})}
    expected_notes = [USE_AS_DICTIONARY_BAD_TYPE, USE_AS_DICTIONARY_BAD_TYPE]
