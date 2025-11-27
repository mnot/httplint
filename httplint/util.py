from binascii import b2a_hex
from datetime import timedelta
import locale
import time
from typing import List
import unittest
from urllib.parse import urlsplit, urlunsplit, quote as urlquote

from httplint.i18n import translate, format_timedelta


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


def markdown_list(inlist: List[str], markup: str = "") -> str:
    """
    Format a list of strings into markdown.
    """
    return "\n".join([f"- {markup}{i}{markup}" for i in inlist])


def relative_time(utime: float, now: float, show_sign: int = 1) -> str:
    """
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
        0 - don't show
        1 - ago / from now  [DEFAULT]
        2 - early / late
    """

    delta_secs = utime - now
    delta = timedelta(seconds=delta_secs)
    if show_sign == 1:
        output = format_timedelta(delta, add_direction=True, threshold=1.2)
    else:
        delta_string = format_timedelta(delta, threshold=1.2)
        if show_sign == 2:
            if delta_secs > 0:
                output = f"{delta_string} {translate('ahead')}"
            else:
                output = f"{delta_string} {translate('behind')}"
        else:
            output = delta_string
    return output


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
            self.assertEqual(relative_time(self.now + delta, self.now), result)
