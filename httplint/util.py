from binascii import b2a_hex
import locale
import time
from typing import Optional, List
import unittest
from urllib.parse import urlsplit, urlunsplit, quote as urlquote


def iri_to_uri(iri: str) -> str:
    "Takes a string that can contain an IRI and return a URI."
    scheme, authority, path, query, frag = urlsplit(iri)
    if ":" in authority:
        host, port = authority.split(":", 1)
        authority = host.encode("idna").decode("ascii") + f":{port}"
    else:
        authority = authority.encode("idna").decode("ascii")
    sub_delims = "!$&'()*+,;="
    pchar = "-.+~" + sub_delims + ":@" + "%"
    path = urlquote(path, safe=pchar + "/")
    quer = urlquote(query, safe=pchar + "/?")
    frag = urlquote(frag, safe=pchar + "/?")
    return urlunsplit((scheme, authority, path, quer, frag))


def f_num(i: int, by1024: bool = False) -> str:
    "Format a number according to the locale."
    if by1024:
        kilo = int(i / 1024)
        mega = int(kilo / 1024)
        giga = int(mega / 1024)
        if giga:
            return locale.format_string("%d", giga, grouping=True) + "g"
        if mega:
            return locale.format_string("%d", mega, grouping=True) + "m"
        if kilo:
            return locale.format_string("%d", kilo, grouping=True) + "k"
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


def prose_list(inlist: List[str], markup: str = "") -> str:
    """
    Format a list of strings into prose.
    """
    length = len(inlist)
    mu = markup
    if length == 0:
        return "(none)"
    if length == 1:
        return f"{mu}{inlist[0]}{mu}"
    if length == 2:
        return f"{mu}{inlist[0]}{mu} and {mu}{inlist[1]}{mu}"
    return (
        f"{', '.join([f'{mu}{i}{mu}' for i in inlist[:-1]])}, and {mu}{inlist[-1]}{mu}"
    )


def relative_time(utime: float, now: Optional[float] = None, show_sign: int = 1) -> str:
    """
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
        0 - don't show
        1 - ago / from now  [DEFAULT]
        2 - early / late
    """

    signs = {
        0: ("0", "", ""),
        1: ("now", "ago", "from now"),
        2: ("none", "behind", "ahead"),
    }

    if now is None:
        now = time.time()
    age = round(now - utime)
    if age == 0:
        return signs[show_sign][0]

    aa = abs(age)
    yrs = int(aa / 60 / 60 / 24 / 365)
    day = int(aa / 60 / 60 / 24) % 365
    hrs = int(aa / 60 / 60) % 24
    mnt = int(aa / 60) % 60
    sec = int(aa % 60)

    if age > 0:
        sign = signs[show_sign][1]
    else:
        sign = signs[show_sign][2]
    if not sign:
        sign = signs[show_sign][0]

    arr = []
    if yrs:
        arr.append(f"{yrs} year{yrs > 1 and 's' or ''}")
    if day:
        arr.append(f"{day} day{day > 1 and 's' or ''}")
    if hrs:
        arr.append(f"{hrs} hour{hrs > 1 and 's' or ''}")
    if mnt:
        arr.append(f"{mnt} minute{mnt > 1 and 's' or ''}")
    if sec:
        arr.append(f"{sec} second{sec > 1 and 's' or ''}")
    arr = arr[:2]  # resolution
    output = ", ".join(arr)
    if show_sign:
        return f"{output} {sign}"
    return output


class RelativeTimeTester(unittest.TestCase):
    minute = 60
    hour = minute * 60
    day = hour * 24
    year = day * 365
    cases = [
        (+year, "1 year from now"),
        (-year, "1 year ago"),
        (+year + 1, "1 year, 1 second from now"),
        (+year + 0.9, "1 year, 1 second from now"),
        (+year + day, "1 year, 1 day from now"),
        (+year + (10 * day), "1 year, 10 days from now"),
        (+year + (90 * day) + (3 * hour), "1 year, 90 days from now"),
        (+(13 * day) - 0.4, "13 days from now"),
    ]

    def setUp(self) -> None:
        self.now = time.time()

    def test_relative_time(self) -> None:
        for delta, result in self.cases:
            self.assertEqual(relative_time(self.now + delta, self.now), result)
