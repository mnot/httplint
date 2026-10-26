"""
Entity-tags for ETag, If-Match, If-None-Match and If-Range.
"""

import re
from typing import Callable, Optional, Tuple

from httplint.field.common import RE_FLAGS
from httplint.field.params import unquote_string
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


def is_entity_tag(value: str) -> bool:
    "Whether ``value`` matches the entity-tag syntax."
    return re.match(rf"^\s*{rfc9110.entity_tag}\s*$", value, RE_FLAGS) is not None


def parse_entity_tag(
    value: str,
    add_note: AddNoteMethodType,
    suppress_syntax: Optional[Callable[[], None]] = None,
) -> Tuple[bool, str]:
    """
    Parse an entity-tag into (weak, opaque-tag), with the opaque tag unquoted.

    The ``W/`` prefix is case-sensitive (RFC 9110, Section 8.8.3). A lower-case ``w/``
    raises ValueError. If the value would be valid with a capital W, the case is its only
    syntax defect: this adds ENTITY_TAG_WEAK_CASE and calls ``suppress_syntax`` (the field's
    ``suppress_syntax_note``), so that the value gets that one note and no BAD_SYNTAX. Any
    other lower-case ``w/`` value is left to the field's syntax check. Quoting isn't checked
    here.
    """
    if value[:2] == "W/":
        return (True, unquote_string(value[2:]))
    if value[:2].lower() == "w/":
        # The syntax is case-sensitive, so test the value as it would be with a capital W.
        if is_entity_tag("W/" + value[2:]):
            add_note(ENTITY_TAG_WEAK_CASE)
            if suppress_syntax is not None:
                suppress_syntax()
        raise ValueError
    return (False, unquote_string(value))


class ENTITY_TAG_WEAK_CASE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s field's entity tag has a lower-case weak indicator."
    _text = """\
An entity tag is weak when it starts with `W/`, and that prefix is case-sensitive: a lower-case
`w/` isn't the weak indicator. Recipients can therefore treat the whole value as an invalid tag,
or as a strong tag that happens to start with `w/`.

See [the HTTP specification](https://www.rfc-editor.org/rfc/rfc9110.html#name-etag) for more
information."""


class ENTITY_TAG_LIST_STAR(Note):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "The %(field_name)s field mixes '*' with entity tags."
    _text = """\
The `*` in the `%(field_name)s` field matches any current representation, so it is only valid
on its own: the field's value is either `*` or a list of entity tags
([RFC 9110, Section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) and
[Section 13.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-none-match)).

Recipients may handle a list that includes both in different ways; send either `*` or the
entity tags."""
