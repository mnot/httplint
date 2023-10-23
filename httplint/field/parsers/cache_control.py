from typing import Tuple, Union

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7234
from httplint.types import AddNoteMethodType
from httplint.field.utils import unquote_string


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
        directive_name = directive_name.lower()
        if directive_name in ["max-age", "s-maxage"]:
            try:
                return (directive_name, int(directive_val))
            except (ValueError, TypeError):
                add_note(BAD_CC_SYNTAX, bad_cc_attr=directive_name)
                raise ValueError  # pylint: disable=raise-missing-from
        return (directive_name, directive_val)


class BAD_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The %(bad_cc_attr)s Cache-Control directive's syntax is incorrect."
    _text = "This value must be an integer."


class CacheControlTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"a=b, c=d", b"e=f", b"g"]
    expected_out = [("a", "b"), ("c", "d"), ("e", "f"), ("g", None)]


class CacheControlCaseTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"A=b, c=D"]
    expected_out = [("a", "b"), ("c", "D")]


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
