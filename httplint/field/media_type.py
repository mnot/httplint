"""
Media types and media ranges, and the notes about their names.
"""

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, Union

from httplint.field.common import RE_FLAGS, syntax_position
from httplint.field.params import parse_params
from httplint.note import Note, categories, levels
from httplint.syntax import rfc6838, rfc9110
from httplint.types import AddNoteMethodType, ParamDictType

if TYPE_CHECKING:
    from httplint.field import HttpField


# restricted-name (RFC 6838, Section 4.2) without its 126-character bound, so that
# over-long names are reported as MEDIA_TYPE_LONG_NAME instead of being lumped in
# with character errors.

RESTRICTED_NAME_UNBOUNDED = (
    rf"(?: {rfc6838.restricted_name_first} {rfc6838.restricted_name_chars}* )"
)


def parse_media_type(
    field_value: str,
    add_note: AddNoteMethodType,
    bad_syntax_note: Optional[Type[Note]] = None,
    ref_uri: Optional[str] = None,
    allow_wildcard: bool = False,
    nostar: Optional[Union[List[str], bool]] = None,
) -> Tuple[str, ParamDictType]:
    """
    Parse a media-type with optional parameters (e.g. ``text/html;charset=utf-8``).

    Returns a tuple of the lowercased media-type and its parameter dict; see
    ``check_media_type`` for the checks applied along the way. ``nostar`` is passed
    through to ``parse_params`` to flag RFC 8187-style ``param*`` keys.
    """
    try:
        media_type, param_str = field_value.split(";", 1)
    except ValueError:
        media_type, param_str = field_value, ""
    media_type = media_type.strip().lower()
    check_media_type(media_type, add_note, bad_syntax_note, ref_uri, allow_wildcard)
    param_dict = parse_params(param_str, add_note, nostar)
    return media_type, param_dict


def parse_media_type_once(
    field: "HttpField[Any]",
    field_value: str,
    add_note: AddNoteMethodType,
    bad_syntax_note: Type[Note],
    **kwargs: Any,
) -> Tuple[str, ParamDictType]:
    """
    parse_media_type() for a field that reports a value that isn't shaped like a media type or
    media range with ``bad_syntax_note``. If that is the value's only syntax defect (it would
    match the field's syntax with the media type swapped for a valid one), the field's generic
    syntax note is dropped, so the defect gets one note. A second defect, e.g. in a parameter,
    still gets the generic note.
    """
    reported = False

    def track(note: Type[Note], category: Optional[Any] = None, **vrs: Any) -> Note:
        nonlocal reported
        if note is bad_syntax_note:
            reported = True
            vrs["position"] = syntax_position(field, field_value)
        return add_note(note, category, **vrs)

    result = parse_media_type(field_value, track, bad_syntax_note, field.reference, **kwargs)
    if reported:
        _, sep, params = field_value.partition(";")
        if field.matches_syntax(f"a/b{sep}{params}"):
            field.suppress_syntax_note()
    return result


def check_media_type(
    media_type: str,
    add_note: AddNoteMethodType,
    bad_syntax_note: Optional[Type[Note]] = None,
    ref_uri: Optional[str] = None,
    allow_wildcard: bool = False,
    check_token: bool = False,
) -> None:
    """
    Check a media-type against the shape HTTP gives it and the naming rules in
    RFC 6838, Section 4.2.

    If ``bad_syntax_note`` is provided, it is emitted (with ``ref_uri`` if given)
    when the value isn't shaped like a media-type at all. When ``allow_wildcard``
    is true the value is treated as a media range, so ``*/*`` and ``type/*`` are
    accepted; otherwise a ``*`` in either position is an error.

    Names that aren't valid HTTP tokens are normally left to the field's own
    syntax check. Callers without one -- Structured Fields, whose members can
    carry any string -- should set ``check_token`` so that they're reported here
    instead.
    """

    def bad_syntax() -> None:
        if bad_syntax_note is None:
            return
        kwargs: Dict[str, Any] = {"value": media_type}
        if ref_uri is not None:
            kwargs["ref_uri"] = ref_uri
        add_note(bad_syntax_note, **kwargs)

    type_name, slash, subtype_name = media_type.partition("/")
    if not (slash and type_name and subtype_name) or "/" in subtype_name:
        bad_syntax()
        return

    names = [type_name, subtype_name]
    if "*" in names:
        # "*/*" and "type/*" are media ranges; "*/subtype" isn't anything.
        if not allow_wildcard or (type_name == "*" and subtype_name != "*"):
            bad_syntax()
            return
        names = [name for name in names if name != "*"]

    tokens = [name for name in names if re.match(rf"^{rfc9110.token}$", name, RE_FLAGS)]
    if len(tokens) != len(names):
        if check_token:
            bad_syntax()
            return
        # Otherwise the field's own syntax check reports it, and RFC 6838 has
        # nothing to add.
        names = tokens

    if any(len(name) > rfc6838.RESTRICTED_NAME_MAX_LEN for name in names):
        add_note(MEDIA_TYPE_LONG_NAME, value=media_type)
    if any(not re.match(rf"^{RESTRICTED_NAME_UNBOUNDED}$", name, RE_FLAGS) for name in names):
        add_note(MEDIA_TYPE_BAD_NAME, value=media_type)


class MEDIA_TYPE_BAD_NAME(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s field's media type name isn't registrable."
    _text = """\
[RFC6838](https://www.rfc-editor.org/rfc/rfc6838.html#section-4.2) requires the type and
subtype names in a media type to start with a letter or a digit, and to use only letters,
digits and the characters `!`, `#`, `$`, `&`, `-`, `^`, `_`, `.` and `+`. `%(value)s`
uses something else.

HTTP's own syntax for media types is more permissive, so recipients are likely to accept
this; however, a media type named this way can't be registered with IANA."""


class MEDIA_TYPE_LONG_NAME(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s field's media type name is too long."
    _text = """\
[RFC6838](https://www.rfc-editor.org/rfc/rfc6838.html#section-4.2) limits the type and
subtype names in a media type to 127 characters each; `%(value)s` is longer than that.

It also recommends keeping them to 64 characters, because longer names run into
implementation limits."""
