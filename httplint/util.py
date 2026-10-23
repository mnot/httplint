import locale
import math
import re
import time
import unittest
from binascii import b2a_hex
from datetime import timedelta
from typing import Any, List
from urllib.parse import quote as urlquote
from urllib.parse import urlsplit, urlunsplit

import idna

from httplint.i18n import format_timedelta, translate
from httplint.note import MarkdownSafe

# What userinfo may contain in a URI besides unreserved characters, RFC 3986 Section 3.2.1;
# "%" is there so that existing escapes survive.
USERINFO_SAFE = "-._~!$&'()*+,;=:%"


def userinfo_escape_growth(iri: str) -> int:
    """
    How many characters the ASCII escaping in authority_to_ascii adds to the URI that
    iri_to_uri makes from `iri`. Before that escaping, the URI's length was the length
    that mattered for limits, and this lets callers keep reporting it.
    """
    userinfo, at, _ = urlsplit(iri).netloc.rpartition("@")
    unsafe = sum(1 for c in userinfo if c.isascii() and not c.isalnum() and c not in USERINFO_SAFE)
    return 2 * unsafe if at else 0


# What both IDNA2003 and UTS #46 treat as a dot between labels.
_LABEL_SEPARATORS = re.compile("[.\u3002\uff0e\uff61]")

# A label longer than this can't be valid: in 63 characters of A-label, NFKC and
# punycode can't make it much shorter. It bounds the work done on hostile input.
_MAX_LABEL_INPUT = 252


def host_to_ascii(host: str) -> str:
    """
    Convert a host to ASCII for DNS, a label at a time: IDNA2008 with Unicode IDNA
    Compatibility Processing (UTS #46) to map case and compatibility characters, but
    without the transitional processing that turns "faß.de" into "fass.de" (a different
    domain). That is what the URL Standard does, and IDNA2008 itself (RFC 5890)
    obsoletes the IDNA2003 that RFC 3986 and RFC 3987 still cite.

    IDNA2008 forbids some code points that UTS #46 and browsers allow (symbols and
    emoji, "_", a hyphen at the start or end of a label). A label with one falls back
    to Python's IDNA2003 codec -- the label, not the host, so that "_dmarc.faß.de" still
    gets the right "faß" -- and is no stricter than before. Hosts that are already
    ASCII go to the codec unchanged. ASCII labels in other hosts are lowercased, as UTS
    #46 does, but not otherwise checked beyond their length. Raises UnicodeError if
    there's a label that nothing accepts.
    """
    if host.isascii():
        return host.encode("idna").decode("ascii")
    labels = _LABEL_SEPARATORS.split(host)
    for index, label in enumerate(labels):
        if not label and (index == 0 or index != len(labels) - 1):  # only a trailing dot
            raise UnicodeError("label empty")
    return ".".join(_label_to_ascii(label) for label in labels)


def _label_to_ascii(label: str) -> str:
    if not label:
        return label
    if label.isascii():
        if len(label) > 63:
            raise UnicodeError("label too long")
        return label.lower()
    if len(label) > _MAX_LABEL_INPUT:
        raise UnicodeError("label too long")
    try:
        mapped = idna.uts46_remap(label, std3_rules=False, transitional=False)
        # The label is now at most 63 characters of A-label, which takes 4 for "xn--"
        # and a character for everything in it.
        if len(mapped) > 59 or "." in mapped:
            raise idna.IDNAError("label unsuitable")
        return idna.alabel(mapped).decode("ascii")
    except idna.IDNAError:
        return label.encode("idna").decode("ascii")


def authority_to_ascii(authority: str) -> str:
    """
    Make an authority ASCII: convert the host (see host_to_ascii), and percent-encode
    anything in the userinfo that a URI can't carry as UTF-8 (non-ASCII characters, RFC 3987
    Section 3.1, and ASCII ones like a space or "@"). The port is left alone.
    """
    userinfo, at, hostport = authority.rpartition("@")
    userinfo = urlquote(userinfo, safe=USERINFO_SAFE)
    if hostport.startswith("["):  # IP-literal; nothing to encode
        return f"{userinfo}{at}{hostport}"
    host, colon, port = hostport.partition(":")
    return f"{userinfo}{at}{host_to_ascii(host)}{colon}{port}"


def iri_to_uri(iri: str) -> str:
    "Takes a string that can contain an IRI and return a URI."
    scheme, authority, path, query, frag = urlsplit(iri)
    authority = authority_to_ascii(authority)
    sub_delims = "!$&'()*+,;="
    pchar = "-.+~" + sub_delims + ":@" + "%"
    path = urlquote(path, safe=pchar + "/")
    quer = urlquote(query, safe=pchar + "/?")
    frag = urlquote(frag, safe=pchar + "/?")
    return urlunsplit((scheme, authority, path, quer, frag))


def f_num(i: int) -> str:
    "Format a number according to the locale."
    return locale.format_string("%d", i, grouping=True)


def display_bytes(inbytes: bytes, encoding: str = "utf-8", truncate: int = 40) -> str:
    """
    Format arbitrary input bytes for display.

    Printable Unicode characters are displayed without modification;
    everything else is shown as escaped hex.
    """
    instr = inbytes.decode(encoding, "backslashreplace")
    out = []
    for char in instr[:truncate]:
        if not char.isprintable():
            char = rf"\x{b2a_hex(char.encode(encoding)).decode('ascii')}"
        out.append(char)
    return "".join(out)


# Backtick, NUL, and every character str.splitlines() treats as a line break
# (\r \n \v \f \x1c-\x1e \x85 U+2028 U+2029); Markdown parsers differ on
# which of these end a paragraph, so strip them all.
_INLINE_UNSAFE_RE = re.compile("[`\\x00\\n\\r\\x0b\\x0c\\x1c-\\x1e\\x85\\u2028\\u2029]")


def inline_safe(value: str) -> str:
    """
    Strip characters from a wire-supplied value that could corrupt a
    single-line Markdown construct (a code span, a bold marker) it's
    about to be embedded in: backticks, which could close a hand-built
    code span early, and line breaks, which end the paragraph such a
    construct depends on staying inside -- an inline span can't survive
    a paragraph break, unlike an indented block (see markdown_context).
    """
    return _INLINE_UNSAFE_RE.sub("", value)


def markdown_list(inlist: List[str], markup: str = "") -> MarkdownSafe:
    """
    Format a list of strings into Markdown.

    Each item has backticks stripped so wire-supplied content cannot
    close the surrounding `markup` span. The result is MarkdownSafe so
    Note._get_detail preserves the structural markup on interpolation.
    """
    safe = [inline_safe(i) for i in inlist]
    return MarkdownSafe("\n".join(f"- {markup}{i}{markup}" for i in safe))


def markdown_context(text: str, index: int, context_chars: int = 20) -> MarkdownSafe:
    """
    Format an excerpt of text around a character index as an indented
    Markdown code block, with a pointer line underneath marking the index.

    The block is delimited by indentation, not backticks, so embedded
    backticks in wire-supplied text can't break out of it; Note._get_detail
    still HTML-escapes its content via Markdown's own indented-block
    handling on interpolation. Every line of the excerpt gets its own
    indent -- an excerpt can itself contain a raw newline (e.g. from a
    decoded Structured Field Byte Sequence), and indentation only holds a
    block together for as long as every line carries it; an unindented
    line ends the block early and falls through to ordinary, unescaped
    paragraph parsing.
    """
    start = max(0, index - context_chars)
    end = min(len(text), index + context_chars)
    excerpt = text[start:end]
    offset = index - start

    # The pointer goes under the line that holds the index, at its column within that line.
    lines = excerpt.splitlines(keepends=True)
    if not lines or lines[-1].splitlines()[:1] != [lines[-1]]:
        lines.append("")  # excerpt is empty or ends with a line break
    line_start = 0
    for pointer_line, line in enumerate(lines):
        if offset < line_start + len(line) or pointer_line == len(lines) - 1:
            break
        line_start += len(line)
    pointer = " " * (offset - line_start) + "^"

    text_lines = [line.splitlines()[0] if line.splitlines() else "" for line in lines]
    text_lines.insert(pointer_line + 1, pointer)
    indented = "\n".join(f"    {line}" for line in text_lines)
    return MarkdownSafe(f"\n\n{indented}")


# RFC 9111 Section 1.2.2: delta-seconds beyond 2^31 are treated as 2^31.
MAX_DELTA_SECONDS = 2147483648

# Largest span timedelta can represent; RelativeTime caps display here.
MAX_TIMEDELTA_SECONDS = timedelta.max.days * 86400  # symmetric with timedelta.min


class RelativeTime:
    def __init__(self, utime: float, now: float, show_sign: int = 1) -> None:
        self.utime = utime
        self.now = now
        self.show_sign = show_sign

    def _delta_secs(self) -> float:
        try:
            delta_secs = float(self.utime - self.now)
        except OverflowError:
            delta_secs = math.inf if self.utime > self.now else -math.inf
        if math.isnan(delta_secs):
            return 0
        return max(-MAX_TIMEDELTA_SECONDS, min(MAX_TIMEDELTA_SECONDS, delta_secs))

    def __str__(self) -> str:
        delta_secs = self._delta_secs()
        delta = timedelta(seconds=delta_secs)
        if self.show_sign == 1:
            output = format_timedelta(delta, add_direction=True, threshold=1.2)
        else:
            delta_string = format_timedelta(delta, threshold=1.2)
            if self.show_sign == 2:
                if delta_secs > 0:
                    output = f"{delta_string} {translate('ahead')}"
                else:
                    output = f"{delta_string} {translate('behind')}"
            else:
                output = delta_string
        return output

    def __repr__(self) -> str:
        return f"RelativeTime({self.utime}, {self.now}, {self.show_sign})"


def relative_time(utime: float, now: float, show_sign: int = 1) -> Any:
    """
    Given two times, return a object that explains how far apart they are.
    show_sign can be:
        0 - don't show
        1 - ago / from now  [DEFAULT]
        2 - early / late
    """
    return RelativeTime(utime, now, show_sign)


class RelativeTimeTester(unittest.TestCase):
    minute = 60
    hour = minute * 60
    day = hour * 24
    year = day * 365
    cases = [
        (+year, "in 12 months"),
        (-year, "12 months ago"),
        (+year + 1, "in 12 months"),
        (+year + 0.9, "in 12 months"),
        (+year + day, "in 12 months"),
        (+year + (10 * day), "in 12 months"),
        (+year + (90 * day) + (3 * hour), "in 1 year"),
        (+(13 * day) - 0.4, "in 2 weeks"),
    ]

    def setUp(self) -> None:
        self.now = time.time()

    def test_relative_time(self) -> None:
        for delta, result in self.cases:
            self.assertEqual(str(relative_time(self.now + delta, self.now)), result)
