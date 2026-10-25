"""
Parameter lists (``;name=value``): splitting, parsing and the notes they raise.
"""

import re
from typing import List, Optional, Set, Tuple, Union
from urllib.parse import unquote as urlunquote

from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType


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

    ``item`` is arbitrary, so this can backtrack quadratically; ``parse_params`` uses
    ``split_params`` instead.
    """
    if not instr:
        return []
    return [h.strip() for h in re.findall(rf"{item}(?={split}|\s*$)", instr, re.VERBOSE)]


_TOKEN_RE = re.compile(rfc9110.token, re.VERBOSE)
_PARAMETER_VALUE_RE = re.compile(rfc9110.parameter_value, re.VERBOSE)
_WHITESPACE_RE = re.compile(r"\s*")


def _param_spans(instr: str, delim: str, bws: bool = False) -> List[Tuple[int, int]]:
    "Where split_params finds its parameters in ``instr``, as (start, end)."
    size = len(instr)
    spans: List[Tuple[int, int]] = []
    pos = 0
    while pos < size:
        name = _TOKEN_RE.match(instr, pos)
        if not name:
            pos += 1
            continue
        name_end = name.end()
        equals = _WHITESPACE_RE.match(instr, name_end).end() if bws else name_end  # type: ignore[union-attr]
        if equals < size and instr[equals] == "=":
            value_start = equals + 1
            if bws:
                value_start = _WHITESPACE_RE.match(instr, value_start).end()  # type: ignore[union-attr]
            value = _PARAMETER_VALUE_RE.match(instr, value_start)
            if value:
                after = _WHITESPACE_RE.match(instr, value.end()).end()  # type: ignore[union-attr]
                if after == size or instr.startswith(delim, after):
                    spans.append((pos, value.end()))
                    pos = value.end()
                    continue
        pos = name_end
    return spans


def split_params(instr: str, delim: str = ";", bws: bool = False) -> List[str]:
    """
    Split a parameter list into its ``name=value`` parameters.

    ``delim`` is a literal separator, optionally surrounded by whitespace; it must not be
    a token character. Text that isn't a parameter followed by a separator or the end of
    the string is skipped, so ``a=b c=d`` yields only ``c=d``. With ``bws``, whitespace is
    allowed on either side of the ``=`` (the BWS of RFC 8288's link-param).

    This is linear, and gives the same results as ``split_string`` called with
    ``rfc9110.parameter``, which backtracked quadratically. A parameter name is always a
    whole run of token characters (``=`` ends it), and a token value can't end early
    before a separator, so a start that fails would fail at every later point in the
    same run; the scan jumps past the run.
    """
    return [instr[start:end] for start, end in _param_spans(instr, delim, bws)]


def _segment_starts(instr: str, delim: str) -> List[int]:
    "Where each non-blank segment between delimiters starts, ignoring delimiters in quotes."
    size = len(instr)
    starts: List[int] = []
    pos = 0
    while pos < size:
        while pos < size and instr[pos].isspace():
            pos += 1
        if pos >= size:
            break
        if not instr.startswith(delim, pos):
            starts.append(pos)
        quoted = False
        while pos < size and (quoted or not instr.startswith(delim, pos)):
            if instr[pos] == "\\" and quoted:
                pos += 1
            elif instr[pos] == '"':
                quoted = not quoted
            pos += 1
        pos += len(delim)
    return starts


def parse_params(
    instr: str,
    add_note: AddNoteMethodType,
    nostar: Optional[Union[List[str], bool]] = None,
    delim: str = ";",
    bws: bool = False,
) -> ParamDictType:
    """
    Parse parameters into a dictionary.

    If a parameter repeats, the first instance is used and the rest are ignored (and
    not checked further), as RFC 8288 does for Link, the Server Timing specification
    for Server-Timing, and the MIME Sniffing Standard for Content-Type. That includes an
    instance that isn't a valid ``name=value`` (``dur=`` or a bare ``dur``) or that is
    rejected (a ``title*`` with a bad value): it's still the first, so a later one
    doesn't take its place.

    Whitespace around the ``=`` isn't allowed, except with ``bws`` (Link, whose link-param
    has BWS there); the key and value are then stripped of it.
    """
    spans = _param_spans(instr, delim, bws)
    valid_starts = {start for start, _ in spans}
    # Instances in order: each parameter, and each segment that starts with a name but
    # isn't one (which the specs count as an instance too).
    instances: List[Tuple[int, str, Optional[Tuple[int, int]]]] = []
    for start, end in spans:
        instances.append((start, instr[start:end].split("=", 1)[0].strip().lower(), (start, end)))
    for start in _segment_starts(instr, delim):
        name = _TOKEN_RE.match(instr, start)
        if name and start not in valid_starts:
            instances.append((start, name.group().lower(), None))
    instances.sort(key=lambda instance: instance[0])

    param_dict: ParamDictType = {}
    seen: Set[str] = set()
    for _, k_norm, span in instances:
        if k_norm in seen:
            add_note(PARAM_REPEATS, param=k_norm)
            continue
        seen.add(k_norm)
        if span is None:
            continue
        key, val = (part.strip() for part in instr[span[0] : span[1]].split("=", 1))
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


class PARAM_REPEATS(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter repeats in the %(field_name)s header."
    _text = """\
Parameters on the `%(field_name)s` field should not repeat; implementations may handle them
differently. Where a specification says, it's the first instance that counts -- for example,
[RFC 8288](https://www.rfc-editor.org/rfc/rfc8288.html#section-3.3) for `Link`, and the
[Server Timing](https://w3c.github.io/server-timing/#the-server-timing-header-field)
specification -- and that is the one used here."""


class PARAM_SINGLE_QUOTED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter on the %(field_name)s header is single-quoted."
    _text = """\
The `%(param)s`'s value on the `%(field_name)s` field starts and ends with a single quote (').
However, single quotes don't mean anything there.

This means that the value will be interpreted as `%(param_val)s`, **not**
`%(param_val_unquoted)s`. If you intend the latter, remove the single quotes."""


class PARAM_STAR_BAD(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s* parameter isn't allowed on the %(field_name)s field."
    _text = """\
Parameters whose names end in '*' are reserved for non-ascii text, as explained in
[RFC8187](https://www.rfc-editor.org/rfc/rfc8187#section-4).

The `%(param)s` parameter on the `%(field_name)s` field does not allow this; you should use
%(param)s without the "*" on the end (and without the associated encoding)."""


class PARAM_STAR_QUOTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The '%(param)s' parameter's value cannot be quoted."
    _text = """\
Parameters whose names end in '*' have values with a specific format, defined in
[RFC8187](https://www.rfc-editor.org/rfc/rfc8187#section-3.2.1), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field has double-quotes around it, which is not
valid."""


class PARAM_STAR_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s parameter's value is invalid."
    _text = """\
Parameters whose names end in '*' have values with a specific format, defined in
[RFC8187](https://www.rfc-editor.org/rfc/rfc8187#section-3.2.1), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field is not valid; it needs to have three
parts, separated by single quotes (')."""


class PARAM_STAR_NOCHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value doesn't define an encoding."
    _text = """\
Parameters whose names end in '*' have values with a specific format, defined in
[RFC8187](https://www.rfc-editor.org/rfc/rfc8187#section-3.2.1), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header doesn't declare its character encoding,
which means that recipients can't understand it. It should be `UTF-8`."""


class PARAM_STAR_CHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value uses an encoding other than UTF-8."
    _text = """\
Parameters whose names end in '*' have values with a specific format, defined in
[RFC8187](https://www.rfc-editor.org/rfc/rfc8187#section-3.2.1), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header uses the `'%(enc)s` encoding, which has
interoperability issues with some browsers. It should be `UTF-8`."""


def split_params_off(value: str) -> Tuple[str, str]:
    """
    Split ``value`` at its first ';' (quoted or not) into (head, parameter text); empty if none.
    Not ``split_params``, which splits a parameter list into its ``name=value`` items.
    """
    head, _, param_str = value.partition(";")
    return head, param_str
