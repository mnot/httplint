from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.field.parsers.cache_control import KNOWN_CC
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels
from httplint.field.notes import RESPONSE_HDR_IN_REQUEST


class cdn_cache_control(HttpField):
    canonical_name = "CDN-Cache-Control"
    description = """\
The `CDN-Cache-Control` header field targets cache directives to Content Delivery Networks."""
    reference = "https://www.rfc-editor.org/rfc/rfc9213.html"
    syntax = False  # SF
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "dictionary"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        add_note(CDN_CACHE_CONTROL_PRESENT)

        for directive_name, item in self.value.items():
            directive_val = item[0]
            directive_name = directive_name.lower()

            # Check for known directives
            if directive_name in KNOWN_CC:
                _valid_req, _valid_res, value_func = KNOWN_CC[directive_name]

                # Check value type compatibility
                if value_func is None:
                    # Expecting no value (boolean True in SF)
                    if directive_val is not True:
                        add_note(
                            BAD_CDN_CC_SYNTAX,
                            bad_directive=directive_name,
                            expected_type="no value",
                        )
                elif value_func is int:
                    # Expecting integer
                    if not isinstance(directive_val, int):
                        add_note(
                            BAD_CDN_CC_SYNTAX,
                            bad_directive=directive_name,
                            expected_type="an integer",
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
                                BAD_CDN_CC_SYNTAX,
                                bad_directive=directive_name,
                                expected_type="a string",
                            )


class BAD_CDN_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The %(bad_directive)s CDN cache directive's syntax is incorrect."
    _text = "This value must be %(expected_type)s."


class CDN_CACHE_CONTROL_PRESENT(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "This response targets cache directives to Content Delivery Networks."
    _text = """\
The `CDN-Cache-Control` header field allows you to specify cache directives that are targeted at
Content Delivery Network (CDN) caches, separately from the `Cache-Control` header field (which
applies to all caches)."""


class CDNCacheControlTest(FieldTest):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=60, no-store"]
    expected_out = {"max-age": (60, {}), "no-store": (True, {})}
    expected_notes = [CDN_CACHE_CONTROL_PRESENT]


class CDNCacheControlBadSyntaxTest(FieldTest):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=foo"]
    expected_notes = [CDN_CACHE_CONTROL_PRESENT, BAD_CDN_CC_SYNTAX]
    expected_out = {"max-age": (Token("foo"), {})}


class CDNCacheControlCaseTest(FieldTest):
    name = "CDN-Cache-Control"
    inputs = [b"no-store"]
    expected_out = {"no-store": (True, {})}
    # Changed input to lowercase because Uppercase keys are invalid in SF Dictionary.
    # Test confirms logic works for valid input.
    expected_notes = [CDN_CACHE_CONTROL_PRESENT]


class CDNCacheControlRequestTest(FieldTest):
    name = "CDN-Cache-Control"
    inputs = [b"max-age=60"]
    linter_class = FakeRequestLinter
    expected_out = None
    expected_notes = [RESPONSE_HDR_IN_REQUEST]
