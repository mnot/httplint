from http_sf import Token

from httplint.field import RESPONSE_HDR_IN_REQUEST
from httplint.field.parsers.cache_control import KNOWN_CC
from httplint.field.structured_field import StructuredField
from httplint.field.tests import FakeRequestLinter, FieldTest
from httplint.note import Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFDictionaryType,
)


class cdn_cache_control(StructuredField[ResponseLinterProtocol]):
    canonical_name = "CDN-Cache-Control"
    description = """\
The `CDN-Cache-Control` header field targets cache directives to Content Delivery Networks."""
    reference = "https://www.rfc-editor.org/rfc/rfc9213.html"
    syntax = False  # SF
    category = categories.CACHING
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "dictionary"
    value: SFDictionaryType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        add_note(CDN_CACHE_CONTROL_PRESENT)

        for directive_name, item in self.value.items():
            directive_val = item[0]
            directive_name = directive_name.lower()

            # Check for known directives
            if directive_name in KNOWN_CC:
                _valid_req, _valid_res, value_func, value_type_str = KNOWN_CC[directive_name]

                # Check value type compatibility
                if value_func is None:
                    # Expecting no value (boolean True in SF)
                    if directive_val is not True:
                        add_note(
                            BAD_CDN_CC_TYPE,
                            bad_directive=directive_name,
                            expected_type="no value",
                        )
                elif value_func is int:
                    # Expecting integer
                    if not isinstance(directive_val, int):
                        add_note(
                            BAD_CDN_CC_TYPE,
                            bad_directive=directive_name,
                            expected_type=value_type_str,
                        )
                else:
                    # Expecting string (unquote_string in legacy, matches SF String)
                    if not isinstance(directive_val, str):
                        # Some directives like no-cache can be boolean True OR string in Legacy?
                        # SF: no-cache could be True (boolean) or String.
                        if directive_val is True and directive_name in [
                            "no-cache",
                            "private",
                        ]:
                            pass
                        else:
                            add_note(
                                BAD_CDN_CC_TYPE,
                                bad_directive=directive_name,
                                expected_type="a string",
                            )


class BAD_CDN_CC_TYPE(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The %(bad_directive)s CDN cache directive's value is incorrect."
    _text = "The value for this directive must be %(expected_type)s."


class CDN_CACHE_CONTROL_PRESENT(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "This response targets cache directives to Content Delivery Networks."
    _text = """\
The `CDN-Cache-Control` header field allows you to specify cache directives that are targeted at
Content Delivery Network (CDN) caches, separately from the `Cache-Control` header field (which
applies to all caches)."""


class CDNCacheControlTest(FieldTest[ResponseLinterProtocol]):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=60, no-store"]
    expected_out = {"max-age": (60, {}), "no-store": (True, {})}
    expected_notes: NoteClassListType = [CDN_CACHE_CONTROL_PRESENT]


class CDNCacheControlBadSyntaxTest(FieldTest[ResponseLinterProtocol]):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=foo"]
    expected_notes: NoteClassListType = [CDN_CACHE_CONTROL_PRESENT, BAD_CDN_CC_TYPE]
    expected_out = {"max-age": (Token("foo"), {})}


class CDNCacheControlCaseTest(FieldTest[ResponseLinterProtocol]):
    name = "CDN-Cache-Control"
    inputs = [b"no-store"]
    expected_out = {"no-store": (True, {})}
    # Changed input to lowercase because Uppercase keys are invalid in SF Dictionary.
    # Test confirms logic works for valid input.
    expected_notes: NoteClassListType = [CDN_CACHE_CONTROL_PRESENT]


class CDNCacheControlRequestTest(FieldTest[ResponseLinterProtocol]):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=60"]
    linter_class = FakeRequestLinter
    expected_out = None
    expected_notes: NoteClassListType = [RESPONSE_HDR_IN_REQUEST]
