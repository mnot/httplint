import calendar
import re
from email.utils import parsedate as lib_parsedate
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Type, Union
from urllib.parse import SplitResult
from urllib.parse import unquote as urlunquote
from urllib.parse import urljoin, urlsplit

from http_sf import Token

from httplint.note import Note, categories, levels
from httplint.syntax import rfc5234, rfc6838, rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.util import inline_safe

RE_FLAGS = re.VERBOSE | re.IGNORECASE

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
    through to ``parse_params`` to flag RFC 5987-style ``param*`` keys.
    """
    try:
        media_type, param_str = field_value.split(";", 1)
    except ValueError:
        media_type, param_str = field_value, ""
    media_type = media_type.strip().lower()
    check_media_type(media_type, add_note, bad_syntax_note, ref_uri, allow_wildcard)
    param_dict = parse_params(param_str, add_note, nostar)
    return media_type, param_dict


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

    ``item`` is arbitrary, so this can backtrack quadratically; ``parse_params`` uses
    ``split_params`` instead.
    """
    if not instr:
        return []
    return [h.strip() for h in re.findall(rf"{item}(?={split}|\s*$)", instr, re.VERBOSE)]


_TOKEN_RE = re.compile(rfc9110.token, re.VERBOSE)
_PARAMETER_VALUE_RE = re.compile(rfc9110.parameter_value, re.VERBOSE)
_WHITESPACE_RE = re.compile(r"\s*")


def _param_spans(instr: str, delim: str) -> List[Tuple[int, int]]:
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
        if name_end < size and instr[name_end] == "=":
            value = _PARAMETER_VALUE_RE.match(instr, name_end + 1)
            if value:
                after = _WHITESPACE_RE.match(instr, value.end()).end()  # type: ignore[union-attr]
                if after == size or instr.startswith(delim, after):
                    spans.append((pos, value.end()))
                    pos = value.end()
                    continue
        pos = name_end
    return spans


def split_params(instr: str, delim: str = ";") -> List[str]:
    """
    Split a parameter list into its ``name=value`` parameters.

    ``delim`` is a literal separator, optionally surrounded by whitespace; it must not be
    a token character. Text that isn't a parameter followed by a separator or the end of
    the string is skipped, so ``a=b c=d`` yields only ``c=d``.

    This is linear, and gives the same results as ``split_string`` called with
    ``rfc9110.parameter``, which backtracked quadratically. A parameter name is always a
    whole run of token characters (``=`` ends it), and a token value can't end early
    before a separator, so a start that fails would fail at every later point in the
    same run; the scan jumps past the run.
    """
    return [instr[start:end] for start, end in _param_spans(instr, delim)]


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


def _char_set(pattern: str) -> FrozenSet[str]:
    """
    The characters below U+0100 that a single-character regex accepts. That covers
    everything qdtext and quoted-pair allow (they stop at obs-text, U+00FF). Under
    IGNORECASE the regex also accepts a few higher characters that case-fold into that
    range (U+0130, for one); field values are decoded as ASCII or ISO-8859-1, so none
    can occur.
    """
    return frozenset(c for c in map(chr, range(256)) if re.fullmatch(pattern, c, RE_FLAGS))


_QDTEXT = _char_set(rfc9110.qdtext)
_QUOTED_PAIR_CHAR = _char_set(
    rf"(?: {rfc5234.HTAB} | {rfc5234.SP} | {rfc5234.VCHAR} | {rfc9110.obs_text} )"
)


def split_list_field(field_value: str) -> List[str]:
    """
    Split a field value on commas, as the #rule needs.

    Commas inside a quoted-string don't split. A quote that doesn't start a valid
    quoted-string is an ordinary character of its item, so the malformed item reaches the
    field's own syntax check instead of being dropped.

    This is linear; an earlier regex-based version backtracked quadratically.
    """
    size = len(field_value)
    # quote_end[idx]: if inside a quoted-string at idx, the index just after its closing
    # quote, or -1 if it is unterminated or malformed.
    quote_end = [-1] * (size + 2)
    # run_end[idx]: where the run of non-comma characters and quoted-strings starting at
    # idx stops (at a comma or the end).
    run_end = [size] * (size + 1)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == '"':
            quote_end[idx] = idx + 1
            after = quote_end[idx + 1]
            run_end[idx] = run_end[after if after >= 0 else idx + 1]
            continue
        if char in _QDTEXT:
            quote_end[idx] = quote_end[idx + 1]
        elif char == "\\" and idx + 1 < size and field_value[idx + 1] in _QUOTED_PAIR_CHAR:
            quote_end[idx] = quote_end[idx + 2]
        run_end[idx] = idx if char == "," else run_end[idx + 1]
    items: List[str] = []
    pos = 0
    while pos < size:
        stop = run_end[pos]
        item = field_value[pos:stop].strip()
        if item:
            items.append(item)
        pos = stop + 1
    return items


def parse_params(
    instr: str,
    add_note: AddNoteMethodType,
    nostar: Optional[Union[List[str], bool]] = None,
    delim: str = ";",
) -> ParamDictType:
    """
    Parse parameters into a dictionary.

    If a parameter repeats, the first instance is used and the rest are ignored (and
    not checked further), as RFC 8288 does for Link, the Server Timing specification
    for Server-Timing, and the MIME Sniffing Standard for Content-Type. That includes an
    instance that isn't a valid ``name=value`` (``dur=`` or a bare ``dur``) or that is
    rejected (a ``title*`` with a bad value): it's still the first, so a later one
    doesn't take its place.
    """
    spans = _param_spans(instr, delim)
    valid_starts = {start for start, _ in spans}
    # Instances in order: each parameter, and each segment that starts with a name but
    # isn't one (which the specs count as an instance too).
    instances: List[Tuple[int, str, Optional[Tuple[int, int]]]] = []
    for start, end in spans:
        instances.append((start, instr[start:end].split("=", 1)[0].lower(), (start, end)))
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
        key, val = instr[span[0] : span[1]].split("=", 1)
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

    Parameter names come from Structured Field dictionary-key syntax
    ([a-z0-9_.*-]) and are safe to embed directly. Parameter values are
    HTTP input; each is passed through inline_safe (no backticks or line
    breaks) and then always re-wrapped in a
    code span before being embedded here -- including into a known
    param's "desc" template, regardless of whether that template already
    puts `%s` in a span of its own -- so a value can never land in bare
    prose no matter how the template is written. The caller must wrap the
    assembled, now-safe result in MarkdownSafe.
    """
    param_list = []
    for param_name, param_value in params.items():
        safe_value = inline_safe(str(param_value))
        if param_name not in known_params:
            add_note(unknown_param_note, param=param_name)
            param_list.append(f"* `{param_name}`: `{safe_value}`")
        else:
            expected_type = known_params[param_name].get("type")
            if expected_type and not isinstance(param_value, expected_type):
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=param_value,
                )
                param_list.append(f"* `{param_name}`: `{safe_value}`")
                continue

            allowed_values = known_params[param_name].get("values")
            if allowed_values and param_value not in allowed_values:
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=param_value,
                )
                param_list.append(f"* `{param_name}`: `{safe_value}`")
                continue

            if "value_desc" in known_params[param_name]:
                desc = known_params[param_name]["value_desc"].get(param_value)
                if desc:
                    param_list.append(f"* {desc}")
                else:
                    param_list.append(f"* `{param_name}`: `{safe_value}`")
            elif "desc" in known_params[param_name]:
                desc = known_params[param_name]["desc"]
                if "%s" in desc:
                    wrapped = f"`{safe_value}`" if safe_value else ""
                    param_list.append(f"* {desc % wrapped}")
                elif param_value:
                    # A static desc with no %s is a flag-style description,
                    # meant for a truthy value; a falsy one (e.g. hit=?0)
                    # has nothing to report.
                    param_list.append(f"* {desc}")
            else:
                if param_value is True:
                    param_list.append(f"* `{param_name}`")
                else:
                    param_list.append(f"* `{param_name}`: `{safe_value}`")

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


# --- resolve_url: URL resolution shared by Link, Location, Referer, Reporting-Endpoints,
# --- Speculation-Rules and NEL


def resolve_url(base: str, url: str) -> Optional[SplitResult]:
    "Resolve url against base and split it; None if urllib rejects it (e.g., a bad IPv6 host)."
    try:
        return urlsplit(urljoin(base, url))
    except ValueError:
        return None


def is_secure(split: SplitResult) -> bool:
    "Whether a split URL has a secure scheme (https or wss)."
    return split.scheme.lower() in ("https", "wss")
