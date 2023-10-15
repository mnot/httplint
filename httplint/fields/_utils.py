import calendar
from email.utils import parsedate as lib_parsedate
import re
from typing import Dict, List, Union

from urllib.parse import unquote as urlunquote

from httplint.syntax import rfc7230, rfc7231
from httplint.types import AddNoteMethodType
from httplint.fields._notes import (
    PARAM_REPEATS,
    PARAM_SINGLE_QUOTED,
    PARAM_STAR_BAD,
    PARAM_STAR_QUOTED,
    PARAM_STAR_ERROR,
    PARAM_STAR_NOCHARSET,
    PARAM_STAR_CHARSET,
    BAD_DATE_SYNTAX,
    DATE_OBSOLETE,
)

RE_FLAGS = re.VERBOSE | re.IGNORECASE


def parse_http_date(value: str, add_note: AddNoteMethodType) -> int:
    """Parse a HTTP date. Raises ValueError if it's bad."""
    if not re.match(rf"^{rfc7231.HTTP_date}$", value, RE_FLAGS):
        add_note(BAD_DATE_SYNTAX)
        raise ValueError
    if re.match(rf"^{rfc7231.obs_date}$", value, RE_FLAGS):
        add_note(DATE_OBSOLETE)
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
    return [
        h.strip() for h in re.findall(rf"{item}(?={split}|\s*$)", instr, re.VERBOSE)
    ]


def split_list_field(field_value: str) -> List[str]:
    "Split a field field value on commas. needs to conform to the #rule."
    return [
        f.strip()
        for f in re.findall(
            r'((?:[^",]|%s)+)(?=%s|\s*$)'
            % (rfc7230.quoted_string, r"(?:\s*(?:,\s*)+)"),
            field_value,
            RE_FLAGS,
        )
        if f
    ] or []


def parse_params(
    instr: str,
    add_note: AddNoteMethodType,
    nostar: Union[List[str], bool] = None,
    delim: str = ";",
) -> Dict[str, str]:
    """
    Parse parameters into a dictionary.
    """
    param_dict: Dict[str, str] = {}
    for param in split_string(instr, rfc7231.parameter, rf"\s*{delim}\s*"):
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
