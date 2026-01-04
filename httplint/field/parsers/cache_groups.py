from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class cache_groups(HttpField):
    canonical_name = "Cache-Groups"
    description = """\
The `Cache-Groups` header field helps caches group responses together for invalidation."""
    reference = "https://www.rfc-editor.org/rfc/rfc9875.html"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "list"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        bad_types = set()
        for item in self.value:
            # SF List items are (value, parameters) tuples
            val = item[0]
            if not isinstance(val, str):
                bad_types.add(type(val).__name__)

        if bad_types:
            add_note(
                CACHE_GROUPS_BAD_TYPE,
                expected="string",
                got=", ".join(sorted(bad_types)),
            )


class CACHE_GROUPS_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Cache groups need to be strings."
    _text = """\
The `%(field_name)s` header values must be Strings. Found `%(got)s`."""


class CacheGroupsTest(FieldTest):
    name = "Cache-Groups"
    inputs = [b'"group1", "group2"']
    expected_out = [("group1", {}), ("group2", {})]
    expected_notes = []


class CacheGroupsBadTypeTest(FieldTest):
    name = "Cache-Groups"
    inputs = [b'123, "group2"']
    expected_out = [(123, {}), ("group2", {})]
    expected_notes = [CACHE_GROUPS_BAD_TYPE]


class CacheGroupsMultipleBadTypesTest(FieldTest):
    name = "Cache-Groups"
    inputs = [b'123, "group2", ?0']
    expected_out = [(123, {}), ("group2", {}), (False, {})]
    expected_notes = [CACHE_GROUPS_BAD_TYPE]
