from typing import Tuple, Union

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7234
from httplint.types import AddNoteMethodType
from httplint.field.utils import unquote_string


# known Cache-Control directives; assumed to not allow duplicates
# values are (valid_in_requests, valid_in_responses, value_type)
KNOWN_CC = {
    "immutable": (False, True, None),
    "max-age": (True, True, int),
    "max-stale": (True, False, int),
    "min-fresh": (True, False, int),
    "must-revalidate": (False, True, None),
    "must-understand": (False, True, None),
    "no-cache": (True, True, None),  # should allow list of field names
    "no-store": (True, True, None),
    "no-transform": (True, True, None),
    "only-if-cached": (True, False, None),
    "private": (False, True, None),  # should allow list of field names
    "proxy-revalidate": (False, True, None),
    "public": (False, True, None),
    "s-maxage": (False, True, int),
    "stale-if-error": (False, True, int),
    "stale-while-revalidate": (False, True, int),
    "pre-check": (False, True, int),
    "post-check": (False, True, int),
}


class cache_control(HttpField):
    canonical_name = "Cache-Control"
    description = """\
The `Cache-Control` header is used to specify required directives to all caches that
handle the response. It can also occur in requests, but caches have the option of
ignoring it there."""
    reference = f"{rfc7234.SPEC_URL}#header.cache-control"
    syntax = rfc7234.Cache_Control
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, Union[int, str]]:
        try:
            directive_name, directive_val = field_value.split("=", 1)
            directive_val = unquote_string(directive_val)
        except ValueError:
            directive_name = field_value
            directive_val = None
        if directive_name != directive_name.lower():
            add_note(
                CC_MISCAP,
                directive_lower=directive_name.lower(),
                directive=directive_name,
            )
        directive_name = directive_name.lower()

        if directive_name not in KNOWN_CC:
            pass
        elif KNOWN_CC[directive_name][2] is None and directive_val is not None:
            add_note(BAD_CC_SYNTAX, bad_directive=directive_name)
        else:
            try:
                return (directive_name, KNOWN_CC[directive_name][2](directive_val))
            except (ValueError, TypeError):
                add_note(BAD_CC_SYNTAX, bad_directive=directive_name)
                raise ValueError  # pylint: disable=raise-missing-from
        return (directive_name, directive_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        cc_list = [d.lower() for (d, v) in self.value]
        for directive in set(cc_list):
            if directive in KNOWN_CC and cc_list.count(directive) > 1:
                add_note(CC_DUP, directive=directive)

            if (
                self.message.message_type == "request"
                and KNOWN_CC.get(directive, (True, True))[0] is False
            ):
                add_note(
                    CC_WRONG_MESSAGE,
                    directive=directive,
                    message="request",
                    other_message="response",
                )
            if (
                self.message.message_type == "response"
                and KNOWN_CC.get(directive, (True, True))[1] is False
            ):
                add_note(
                    CC_WRONG_MESSAGE,
                    directive=directive,
                    message="response",
                    other_message="request",
                )


class BAD_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The %(bad_directive)s Cache-Control directive's syntax is incorrect."
    _text = "This value must be an integer."


class CC_MISCAP(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s Cache-Control directive has non-lowercase characters."
    _text = """\
Cache-Control directive names are case-insensitive, but some implementations don't
recognize directives that aren't all-lowercase.

Therefore, it's safest to use %(directive_lower)s instead of %(directive)s."""


class CC_DUP(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s Cache-Control directive appears more than once."
    _text = """\
The %(directive)s Cache-Control directive is only defined to appear once; it is used more than
once here, so implementations may use different instances (e.g., the first, or the last),
making their behaviour unpredictable."""


class CC_WRONG_MESSAGE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = (
        "The %(directive)s Cache-Control directive has no meaning in a %(message)s."
    )
    _text = """\
The %(directive)s Cache-Control directive is only defined to appear in %(other_message)
messages; is has no defined meaning in a %(message)."""


class CacheControlTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"a=b, c=d", b"e=f", b"g"]
    expected_out = [("a", "b"), ("c", "d"), ("e", "f"), ("g", None)]


class CacheControlCaseTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"A=b, c=D"]
    expected_out = [("a", "b"), ("c", "D")]
    expected_notes = [CC_MISCAP]


class CacheControlQuotedTest(FieldTest):
    name = "Cache-Control"
    inputs = [b'a="b,c", c=d']
    expected_out = [("a", "b,c"), ("c", "d")]


class CacheControlMaxAgeTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"max-age=5"]
    expected_out = [("max-age", 5)]


class CacheControlBadMaxAgeTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"max-age=foo"]
    expected_notes = [BAD_CC_SYNTAX]
