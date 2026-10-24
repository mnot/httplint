import calendar
import re
import time
from email.utils import parsedate as lib_parsedate
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
from urllib.parse import SplitResult
from urllib.parse import unquote as urlunquote
from urllib.parse import urljoin, urlsplit

from http_sf import Token

from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.syntax import rfc5234, rfc6838, rfc9110
from httplint.types import AddNoteMethodType, LinterProtocol, ParamDictType
from httplint.util import inline_safe, invalid_char_problem, markdown_context

if TYPE_CHECKING:
    from httplint.field import HttpField

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


def parse_http_date(
    value: str,
    add_note: AddNoteMethodType,
    category: Optional[categories] = None,
    now: Optional[float] = None,
) -> int:
    """
    Parse a HTTP date. Raises ValueError if it's bad.

    ``now`` is the reference time (seconds since the epoch) for resolving the
    two-digit year of an rfc850-date, as RFC 9110 Section 5.6.7 requires; it defaults
    to the current time. Callers with a message should pass its ``start_time`` so that
    linting a recorded exchange is repeatable.
    """
    if not re.match(rf"^{rfc9110.HTTP_date}$", value, RE_FLAGS):
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    if re.match(rf"^{rfc9110.obs_date}$", value, RE_FLAGS):
        add_note(DATE_OBSOLETE, category=category)
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    # IMF-fixdate and asctime-date have four-digit years, which parsedate would
    # otherwise treat as two-digit ones ("0000" -> 2000); rfc850-date's own two-digit
    # years are resolved below, not by parsedate's fixed pivot.
    year_match = re.search(r"(?<!\d)\d{4}(?!\d)", value)
    year, month, day, hour, minute, second = date_tuple[:6]
    if year_match:
        year = int(year_match.group())
    else:
        year = _resolve_two_digit_year(
            year % 100, (month, day, hour, minute, second), _time_or_now(now)
        )
    # Out-of-range fields would be silently normalised by timegm.
    if year < 1 or not 1 <= month <= 12 or day < 1 or day > calendar.monthrange(year, month)[1]:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    # A second of 60 is a leap second.
    if hour > 23 or minute > 59 or second > 60:
        add_note(BAD_DATE_SYNTAX, category=category)
        raise ValueError
    return calendar.timegm((year, month, day, hour, minute, second))


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


def split_list_field(
    field_value: str, angle_targets: bool = False, comments: bool = False
) -> List[str]:
    """
    Split a field value on commas, as the #rule needs.

    Commas inside a quoted-string don't split. A quote that doesn't start a valid
    quoted-string is an ordinary character of its item, so the malformed item reaches the
    field's own syntax check instead of being dropped.

    With ``angle_targets``, a ``<...>`` at the start of an item (as in Link) is skipped
    over whole, so commas inside it don't split either. It ends at the first ``>``; if there
    is none, or another ``<`` comes first, the ``<`` is an ordinary character. That last
    rule departs from RFC 8288 Appendix B.2, which takes the target up to the first ``>``:
    ``<a<b,c>`` is two (invalid) items here, not one. The target isn't a valid
    URI-Reference either way, and this keeps ``<a, <b>`` as two items, as before.

    With `comments`, commas inside a parenthesised comment (nested to any depth) don't
    split either; an unmatched "(" is an ordinary character, as with a stray quote.
    ``angle_targets`` has no effect with ``comments``; no field uses both.

    This is linear; an earlier regex-based version backtracked quadratically.
    """
    size = len(field_value)
    # quote_end[idx]: if inside a quoted-string at idx, the index just after its closing
    # quote, or -1 if it is unterminated or malformed.
    quote_end = [-1] * (size + 2)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == '"':
            quote_end[idx] = idx + 1
        elif char in _QDTEXT:
            quote_end[idx] = quote_end[idx + 1]
        elif char == "\\" and idx + 1 < size and field_value[idx + 1] in _QUOTED_PAIR_CHAR:
            quote_end[idx] = quote_end[idx + 2]
    if comments:
        return _split_outside_comments(field_value, quote_end)
    # run_end[idx]: where the run of non-comma characters and quoted-strings starting at
    # idx stops (at a comma or the end).
    run_end = [size] * (size + 1)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == '"':
            after = quote_end[idx + 1]
            run_end[idx] = run_end[after if after >= 0 else idx + 1]
        else:
            run_end[idx] = idx if char == "," else run_end[idx + 1]
    items: List[str] = []
    pos = 0
    # close: the first ">" after the last "<" we looked at; -1 if there is none, -2 if unset.
    # Reusing it is safe: it was the first ">" at or after an earlier "<", so while
    # close >= start (and start only moves forward) no ">" lies between start and close.
    # With no ">" at all (-1), nothing later can be a bracketed target. Searching every
    # time would be quadratic.
    close = -2
    while pos < size:
        stop = run_end[pos]
        if angle_targets and close != -1:
            start = pos
            while start < size and field_value[start].isspace():
                start += 1
            if start < size and field_value[start] == "<":
                if close < start:
                    close = field_value.find(">", start)
                if close != -1 and field_value.find("<", start + 1, close) == -1:
                    stop = run_end[close + 1]
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
        # An empty code span would swallow the next span's delimiters.
        shown_value = f"`{safe_value}`" if safe_value else "(empty)"
        # The notes below put %(value)s in a code span of their own, and an empty value would
        # leave an empty one, so they get a placeholder instead.
        note_value = param_value if str(param_value) else MarkdownSafe("(empty)")
        if param_name not in known_params:
            add_note(unknown_param_note, param=param_name)
            param_list.append(f"* `{param_name}`: {shown_value}")
        else:
            expected_type = known_params[param_name].get("type")
            if expected_type and not sf_type_matches(param_value, expected_type):
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=note_value,
                )
                param_list.append(f"* `{param_name}`: {shown_value}")
                continue

            allowed_values = known_params[param_name].get("values")
            if allowed_values and param_value not in allowed_values:
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=note_value,
                )
                param_list.append(f"* `{param_name}`: {shown_value}")
                continue

            if "value_desc" in known_params[param_name]:
                desc = known_params[param_name]["value_desc"].get(param_value)
                if desc:
                    param_list.append(f"* {desc}")
                else:
                    param_list.append(f"* `{param_name}`: {shown_value}")
            elif "desc" in known_params[param_name]:
                desc = known_params[param_name]["desc"]
                if "%s" in desc:
                    wrapped = f"`{safe_value}`" if safe_value else "(empty)"
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
                    param_list.append(f"* `{param_name}`: {shown_value}")

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


# ---- Content negotiation helpers: q-values and Vary coverage ----------------------------


class BAD_Q_VALUE(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "The q value on '%(item)s' is invalid."
    _text = """\
The `q` parameter must be a decimal number between 0 and 1, with at most 3 digits after the
decimal point (for example, `0.5`). A sign, an exponent, quotes, or a missing leading digit
aren't allowed."""


def _q_is_quoted(raw_params: str) -> bool:
    "Is the first q parameter in ``raw_params`` a quoted-string?"
    for segment in split_params(raw_params):
        name, _, value = segment.partition("=")
        if name.lower() == "q":
            return value.startswith('"')
    return False


def parse_qvalue(
    params: ParamDictType,
    add_note: Optional[AddNoteMethodType],
    raw_params: str = "",
    **note_vars: Any,
) -> Optional[float]:
    """
    Remove the ``q`` parameter from ``params`` and return it as a float, or None if it
    is absent or invalid.

    The value must match ``rfc9110.qvalue``. An invalid value is reported with
    ``BAD_Q_VALUE`` (passing ``note_vars`` to it, which should include ``item``), unless
    ``add_note`` is None; use that where the field's syntax check has already flagged it.

    ``parse_params`` unquotes values, but a q-value can't be a quoted-string; pass the
    parameter text as ``raw_params`` to have that detected too.
    """
    if "q" not in params:
        return None
    q_str = params.pop("q")
    if (
        q_str is not None
        and not _q_is_quoted(raw_params)
        and re.fullmatch(rfc9110.qvalue, q_str, RE_FLAGS)
    ):
        return float(q_str)
    if add_note is not None:
        add_note(BAD_Q_VALUE, **note_vars)
    return None


def vary_covers(message: Any, name: str) -> bool:
    """
    Does the message's Vary header cover the request header ``name``? That is the case
    if it lists the name (case-insensitively) or is ``*``.

    Callers check cacheability first, and ``Vary: *`` makes a response uncacheable, so the
    ``*`` branch is rarely reached; it keeps the helper correct for callers that don't.
    """
    vary_values = message.headers.parsed.get("vary") or ()
    values = {str(v).lower() for v in vary_values}
    return "*" in values or name.lower() in values


# --- resolve_url: URL resolution shared by Link, Location, Referer, Reporting-Endpoints,
# --- Speculation-Rules and NEL


def resolve_url(url: str, base: str = "") -> Optional[SplitResult]:
    "Resolve url against base (if any) and split it; None if urllib rejects it (e.g., bad IPv6)."
    try:
        return urlsplit(urljoin(base, url))
    except ValueError:
        return None


def is_secure(split: SplitResult) -> bool:
    "Whether a split URL has a secure scheme (https or wss)."
    return split.scheme.lower() in ("https", "wss")


# --- parse_delta_seconds: non-negative integer field values ---------------------------------


def parse_digits(value: str, max_digits: int = 20) -> Optional[int]:
    """
    Parse `value` as DIGIT+ (ASCII only; no sign, underscore or whitespace), or return None if it
    isn't, or has more than `max_digits` significant digits (leading zeros don't count).

    This keeps int()'s leniency and its 4300-digit limit away from wire values.
    """
    if value.isascii() and value.isdigit():
        digits = value.lstrip("0") or "0"
        if len(digits) <= max_digits:
            return int(digits)
    return None


def parse_delta_seconds(
    value: str,
    add_note: AddNoteMethodType,
    bad_note: Type[Note],
    max_digits: int = 20,
    **note_vars: Any,
) -> Optional[int]:
    """
    Parse `value` with parse_digits(), as used for delta-seconds and similar values.

    On failure, add `bad_note` (with `note_vars`) and return None. Range checks stay with the
    caller.
    """
    result = parse_digits(value, max_digits)
    if result is None:
        add_note(bad_note, **note_vars)
    return result


def is_negative_integer(value: str) -> bool:
    "True if `value` is '-' followed by ASCII DIGIT+; for choosing a more specific note."
    magnitude = value[1:]
    return value.startswith("-") and magnitude.isascii() and magnitude.isdigit()


# --- parse_entity_tag: entity-tags for ETag, If-Match, If-None-Match and If-Range ---------------


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
    _summary = "The %(field_name)s field mixes `*` with entity tags."
    _text = """\
The `*` in the `%(field_name)s` field matches any current representation, so it is only valid
on its own: the field's value is either `*` or a list of entity tags
([RFC 9110, Section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) and
[Section 13.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-none-match)).

Recipients may handle a list that includes both in different ways; send either `*` or the
entity tags."""


# --- known_reporting_endpoints: endpoint names for CSP, COEP, COOP and NEL ---------------------


def report_to_groups(message: LinterProtocol) -> Set[str]:
    "Names of the groups defined by `Report-To` (the group member, which defaults to `default`)."
    groups: Set[str] = set()
    report_to_value = message.headers.parsed.get("report-to")
    if not isinstance(report_to_value, list):
        return groups
    for group in report_to_value:
        if not isinstance(group, dict):
            continue
        name = group.get("group", "default")
        if isinstance(name, str):
            groups.add(name)
    return groups


def known_reporting_endpoints(message: LinterProtocol, include_report_to: bool = False) -> Set[str]:
    """
    Names of the endpoints defined by `Reporting-Endpoints`; with `include_report_to`, the
    groups defined by `Report-To` as well.
    """
    endpoints_field = message.headers.parsed.get("reporting-endpoints")
    known: Set[str] = set(endpoints_field.keys()) if endpoints_field else set()
    if include_report_to:
        known |= report_to_groups(message)
    return known


# --- is_integer, sf_type_matches: Booleans aren't integers in JSON and Structured Fields -------


def is_integer(value: Any) -> bool:
    "True if `value` is an integer. Python's bool is an int subclass, but JSON and SF's aren't."
    return isinstance(value, int) and not isinstance(value, bool)


def sf_type_matches(value: Any, expected: Any) -> bool:
    "isinstance(), except that a bool only matches if bool itself is expected."
    types = expected if isinstance(expected, tuple) else (expected,)
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def is_number(value: Any) -> bool:
    "True if `value` is an int or a float, but not a bool."
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --- _split_outside_comments: comma splitting that respects "(" comments ")" -------------------


def _split_outside_comments(field_value: str, quote_end: List[int]) -> List[str]:
    """
    Split on commas outside quoted-strings (per `quote_end`, see `split_list_field`) and
    comments. Comments nest, and a quoted-pair inside one can escape a parenthesis; a "(" with
    no matching ")" is an ordinary character.

    Linear: `after_comment` is filled right to left in one pass, then the value is scanned once.
    """
    size = len(field_value)
    # after_comment[idx]: scanning from idx inside a comment (one level deep), the index just
    # after the ")" that closes it, or -1 if there is none. A comment's end, for the "(" at
    # idx, is after_comment[idx + 1].
    after_comment = [-1] * (size + 2)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == ")":
            after_comment[idx] = idx + 1
        elif char == "(":
            # The nested comment ends at after_comment[idx + 1]; carry on from there.
            nested = after_comment[idx + 1]
            after_comment[idx] = after_comment[nested] if nested >= 0 else -1
        elif char == "\\" and idx + 1 < size and field_value[idx + 1] in _QUOTED_PAIR_CHAR:
            after_comment[idx] = after_comment[idx + 2]
        else:
            after_comment[idx] = after_comment[idx + 1]

    items: List[str] = []
    item_start = 0
    idx = 0
    while idx < size:
        char = field_value[idx]
        if char == ",":
            item = field_value[item_start:idx].strip()
            if item:
                items.append(item)
            item_start = idx + 1
            idx += 1
        elif char == '"':
            after = quote_end[idx + 1]
            idx = after if after >= 0 else idx + 1
        elif char == "(":
            after = after_comment[idx + 1]
            idx = after if after >= 0 else idx + 1
        else:
            idx += 1
    item = field_value[item_start:].strip()
    if item:
        items.append(item)
    return items


# --- two-digit years: reference time for parse_http_date ---


def _time_or_now(now: Optional[float]) -> time.struct_time:
    "The reference time as UTC fields; the current time if ``now`` is missing or unusable."
    if now is not None:
        try:
            return time.gmtime(now)
        except (OverflowError, OSError, ValueError):
            pass
    return time.gmtime()


def _resolve_two_digit_year(
    two_digits: int, rest: Tuple[int, int, int, int, int], now: time.struct_time
) -> int:
    """
    The year for a two-digit rfc850-date year, per RFC 9110 Section 5.6.7: a timestamp
    that appears to be more than 50 years in the future is the most recent past year
    with the same last two digits.

    ``rest`` is (month, day, hour, minute, second). Comparing those against ``now``
    rather than building a date 50 years on keeps 29 February from being a special case.
    """
    limit_year = now.tm_year + 50
    year = limit_year - (limit_year - two_digits) % 100
    now_rest = (now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
    if year == limit_year and rest > now_rest:
        year -= 100
    return year
