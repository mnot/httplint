"""
Constants and helpers shared by the field helper modules.
"""

import re
from typing import TYPE_CHECKING, Any

from httplint.note import MarkdownSafe
from httplint.util import inline_safe, invalid_char_problem, markdown_context

if TYPE_CHECKING:
    from httplint.field import HttpField


RE_FLAGS = re.VERBOSE | re.IGNORECASE


def syntax_position(field: "HttpField[Any]", value: str) -> MarkdownSafe:
    """
    For a specific note that stands in for BAD_SYNTAX_DETAILED: where ``value`` stops matching
    the field's syntax, in the same form (the problem character and an excerpt). It is empty if
    no part of the value matches, where the generic note has no position either, and otherwise
    starts with a blank line, to follow a paragraph of text.
    """
    patterns = field._syntax_patterns()  # pylint: disable=protected-access
    match = patterns[1].match(value) if patterns else None
    if not match:
        return MarkdownSafe("")
    index = match.end()
    problem = inline_safe(invalid_char_problem(value, index))
    return MarkdownSafe(f"\n\n`{problem}`\n{markdown_context(value, index)}")
