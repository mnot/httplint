import calendar
from email.utils import parsedate as lib_parsedate
import re
from typing import Optional, List, Union, Dict, Any, Type

from urllib.parse import unquote as urlunquote

from http_sf import Token

from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.note import Note, categories, levels


RE_FLAGS = re.VERBOSE | re.IGNORECASE


def parse_http_date(
    value: str, add_note: AddNoteMethodType, category: Optional[categories] = None
) -> int:
    """Parse a HTTP date. Raises ValueError if it's bad."""
    if not re.match(rf"^{rfc9110.HTTP_date}$", value, RE_FLAGS):
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    if re.match(rf"^{rfc9110.obs_date}$", value, RE_FLAGS):
        add_note(DATE_OBSOLETE, category=category)
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        raise ValueError
    # http://sourceforge.net/tracker/index.php?func=detail&aid=1194222&group_id=5470&atid=105470
    if date_tuple[0] < 100:
        if date_tuple[0] > 68:
            date_tuple = (date_tuple[0] + 1900,) + date_tuple[1:]
        else:
            date_tuple = (date_tuple[0] + 2000,) + date_tuple[1:]
    return calendar.timegm(date_tuple)


def unquote_string(instr: str) -> str:
    """
    Unquote a unicode string; does NOT unquote control characters.

    @param instr: string to be unquoted
    @type instr: unicode
    @return: unquoted string
    @rtype: unicode
    """
    instr = str(instr).strip()
    if not instr or instr == "*":
        return instr
    if instr[0] == instr[-1] == '"':
        ninstr = instr[1:-1]
        instr = re.sub(r"\\(.)", r"\1", ninstr)
    return instr


def split_string(instr: str, item: str, split: str) -> List[str]:
    """
    Split instr as a list of items separated by splits.

    @param instr: string to be split
    @param item: regex for item to be split out
    @param split: regex for splitter
    @return: list of strings
    """
    if not instr:
        return []
    return [h.strip() for h in re.findall(rf"{item}(?={split}|\s*$)", instr, re.VERBOSE)]


def split_list_field(field_value: str) -> List[str]:
    "Split a field field value on commas. needs to conform to the #rule."
    return [
        f.strip()
        for f in re.findall(
            r'((?:[^",]|%s)+)(?=%s|\s*$)' % (rfc9110.quoted_string, r"(?:\s*(?:,\s*)+)"),
            field_value,
            RE_FLAGS,
        )
        if f
    ] or []


def parse_params(
    instr: str,
    add_note: AddNoteMethodType,
    nostar: Optional[Union[List[str], bool]] = None,
    delim: str = ";",
) -> ParamDictType:
    """
    Parse parameters into a dictionary.
    """
    param_dict: ParamDictType = {}
    for param in split_string(instr, rfc9110.parameter, rf"\s*{delim}\s*"):
        try:
            key, val = param.split("=", 1)
        except ValueError:
            param_dict[param.lower()] = None
            continue
        k_norm = key.lower()
        if k_norm in param_dict:
            add_note(PARAM_REPEATS, param=k_norm)
        if val[0] == val[-1] == "'":
            add_note(
                PARAM_SINGLE_QUOTED,
                param=k_norm,
                param_val=val,
                param_val_unquoted=val[1:-1],
            )
        if key[-1] == "*":
            if nostar is True or (nostar and k_norm[:-1] in nostar):
                add_note(PARAM_STAR_BAD, param=k_norm[:-1])
            else:
                if val[0] == '"' and val[-1] == '"':
                    add_note(PARAM_STAR_QUOTED, param=k_norm)
                    val = val[1:-1]
                try:
                    enc, lang, esc_v = val.split("'", 3)
                except ValueError:
                    add_note(PARAM_STAR_ERROR, param=k_norm)
                    continue
                enc = enc.lower()
                lang = lang.lower()
                if enc == "":
                    add_note(PARAM_STAR_NOCHARSET, param=k_norm)
                    continue
                if enc not in ["utf-8"]:
                    add_note(PARAM_STAR_CHARSET, param=k_norm, enc=enc)
                    continue
                unq_v = urlunquote(esc_v)
                param_dict[k_norm] = unq_v
        else:
            param_dict[k_norm] = unquote_string(val)
    return param_dict


def check_sf_params(
    params: Dict[str, Any],
    known_params: Dict[str, Dict[str, Any]],
    add_note: AddNoteMethodType,
    unknown_param_note: Type[Note],
    bad_param_val_note: Type[Note],
) -> str:
    """
    Format parameters for a clause, checking validity against known_params.
    """
    param_list = []
    for param_name, param_value in params.items():
        if param_name not in known_params:
            add_note(unknown_param_note, param=param_name)
            param_list.append(f"* `{param_name}`: `{param_value}`")
        else:
            expected_type = known_params[param_name].get("type")
            if expected_type and not isinstance(param_value, expected_type):
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=param_value,
                )
                param_list.append(f"* `{param_name}`: `{param_value}`")
                continue

            allowed_values = known_params[param_name].get("values")
            if allowed_values and param_value not in allowed_values:
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=param_value,
                )
                param_list.append(f"* `{param_name}`: `{param_value}`")
                continue

            if "value_desc" in known_params[param_name]:
                desc = known_params[param_name]["value_desc"].get(param_value)
                if desc:
                    param_list.append(f"* {desc}")
                else:
                    param_list.append(f"* `{param_name}`: `{param_value}`")
            elif "desc" in known_params[param_name]:
                if param_value is True:
                    param_list.append(f"* {known_params[param_name]['desc']}")
                else:
                    param_list.append(f"* {known_params[param_name]['desc'] % param_value}")
            else:
                if param_value is True:
                    param_list.append(f"* `{param_name}`")
                else:
                    param_list.append(f"* `{param_name}`: `{param_value}`")

    return "\n".join(param_list)


def check_sf_item_token(
    field_value: Any,
    valid_tokens: List[Token],
    add_note: AddNoteMethodType,
    valid_note: Type[Note],
    invalid_note: Type[Note],
    **kwargs: Any,
) -> None:
    """
    Check if a Structured Field Item is a Token and one of the valid tokens.
    """
    if isinstance(field_value, tuple):
        val = field_value[0]
        if isinstance(val, Token):
            if val in valid_tokens:
                add_note(valid_note, value=val, **kwargs)
            else:
                add_note(invalid_note, value=val, **kwargs)
        else:
            add_note(invalid_note, value=val, **kwargs)
    else:
        add_note(invalid_note, value=field_value, **kwargs)


class PARAM_REPEATS(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter repeats in the %(field_name)s header."
    _text = """\
Parameters on the %(field_name)s field should not repeat; implementations may handle them
differently."""


class PARAM_SINGLE_QUOTED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter on the %(field_name)s header is single-quoted."
    _text = """\
The `%(param)s`'s value on the %(field_name)s field starts and ends with a single quote (').
However, single quotes don't mean anything there.

This means that the value will be interpreted as `%(param_val)s`, **not**
`%(param_val_unquoted)s`. If you intend the latter, remove the single quotes."""


class PARAM_STAR_BAD(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s* parameter isn't allowed on the %(field_name)s field."
    _text = """\
Parameter values that end in '*' are reserved for non-ascii text, as explained in
[RFC5987](https://www.rfc-editor.org/rfc/rfc5987).

The `%(param)s` parameter on the `%(field_name)s` field does not allow this; you should use
%(param)s without the "*" on the end (and without the associated encoding)."""


class PARAM_STAR_QUOTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The '%(param)s' parameter's value cannot be quoted."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](https://www.rfc-editor.org/rfc/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field has double-quotes around it, which is not
valid."""


class PARAM_STAR_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s parameter's value is invalid."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](https://www.rfc-editor.org/rfc/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field is not valid; it needs to have three
parts, separated by single quotes (')."""


class PARAM_STAR_NOCHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value doesn't define an encoding."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](https://www.rfc-editor.org/rfc/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header doesn't declare its character encoding,
which means that recipients can't understand it. It should be `UTF-8`."""


class PARAM_STAR_CHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value uses an encoding other than UTF-8."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](https://www.rfc-editor.org/rfc/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header uses the `'%(enc)s` encoding, which has
interoperability issues with some browsers. It should be `UTF-8`."""


class BAD_DATE_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header's value isn't a valid date."
    _text = """\
HTTP dates have specific syntax, and sending an invalid date can cause a number of problems,
especially with caching. Common problems include sending "1 May" instead of "01 May" (the month
is a fixed-width field), and sending a date in a timezone other than GMT.

See [the HTTP specification](https://www.rfc-editor.org/rfc/rfc9110.html#name-date-time-formats) for more
information."""


class DATE_OBSOLETE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header's value uses an obsolete format."
    _text = """\
HTTP has a number of defined date formats for historical reasons. This header is using an old
format that are now obsolete. See [the
specification](https://www.rfc-editor.org/rfc/rfc9110.html#name-obsolete-date-formats) for more information.
"""
