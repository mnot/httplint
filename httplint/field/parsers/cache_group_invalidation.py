from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class cache_group_invalidation(HttpField):
    canonical_name = "Cache-Group-Invalidation"
    description = """\
The `Cache-Group-Invalidation` header field allows a response to invalidate a group of cached
responses."""
    reference = "https://www.rfc-editor.org/rfc/rfc9875.html"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "list"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        # Check if the method is safe
        request = getattr(self.message, "related", None)
        if request and hasattr(request, "method"):
            if request.method in ["GET", "HEAD", "OPTIONS", "TRACE"]:
                add_note(CACHE_GROUP_INVALIDATION_IGNORED, method=request.method)

        bad_types = set()
        for item in self.value:
            # SF List items are (value, parameters) tuples
            val = item[0]
            if not isinstance(val, str):
                bad_types.add(type(val).__name__)

        if bad_types:
            add_note(
                CACHE_GROUP_INVALIDATION_BAD_TYPE,
                expected="string",
                got=", ".join(sorted(bad_types)),
            )


class CACHE_GROUP_INVALIDATION_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Cache groups need to be strings."
    _text = """\
The `%(field_name)s` header values must be Strings. Found `%(got)s`."""


class CACHE_GROUP_INVALIDATION_IGNORED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Cache-Group-Invalidation header is ignored for %(method)s requests."
    _text = """\
The `Cache-Group-Invalidation` header is only processed for unsafe methods (like POST, PUT, DELETE).
It will be ignored for `%(method)s` requests."""


class CacheGroupInvalidationTest(FieldTest):
    name = "Cache-Group-Invalidation"
    inputs = [b'"group1"']
    expected_out = [("group1", {})]

    def setUp(self) -> None:
        super().setUp()

        class MockRequest:
            method = "POST"

        self.message.related = MockRequest()  # type: ignore

    expected_notes = []


class CacheGroupInvalidationIgnoredTest(FieldTest):
    name = "Cache-Group-Invalidation"
    inputs = [b'"group1"']
    expected_out = [("group1", {})]

    def setUp(self) -> None:
        super().setUp()

        class MockRequest:
            method = "GET"

        self.message.related = MockRequest()  # type: ignore

    expected_notes = [CACHE_GROUP_INVALIDATION_IGNORED]


class CacheGroupInvalidationBadTypeTest(FieldTest):
    name = "Cache-Group-Invalidation"
    inputs = [b"123"]
    expected_out = [(123, {})]

    def setUp(self) -> None:
        super().setUp()

        # Ensure check passes (unsafe method)
        class MockRequest:
            method = "POST"

        self.message.related = MockRequest()  # type: ignore

    expected_notes = [CACHE_GROUP_INVALIDATION_BAD_TYPE]


class CacheGroupInvalidationMultipleBadTypesTest(FieldTest):
    name = "Cache-Group-Invalidation"
    inputs = [b'123, "group2", ?0']
    expected_out = [(123, {}), ("group2", {}), (False, {})]

    def setUp(self) -> None:
        super().setUp()

        class MockRequest:
            method = "POST"

        self.message.related = MockRequest()  # type: ignore

    expected_notes = [CACHE_GROUP_INVALIDATION_BAD_TYPE]
