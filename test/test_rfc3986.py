import re
import time
import unittest
from typing import List, Optional, Tuple

from httplint.field.parsers.origin import BAD_ORIGIN_SYNTAX, OriginValue
from httplint.field.tests import FieldTest
from httplint.field import BAD_SYNTAX
from httplint.syntax import rfc3986
from httplint.types import NoteClassListType, RequestLinterProtocol


def matches(rule: str, value: str) -> bool:
    return re.match(rf"^{rule}$", value, re.VERBOSE) is not None


IPV6_VALID = [
    "::",
    "::1",
    "1::",
    "1::2",
    "::1:2:3:4:5:6:7",
    "1:2:3:4:5:6:7::",
    "1:2:3:4:5:6:7:8",
    "1:2:3:4:5:6:1.2.3.4",
    "::1.2.3.4",
    "::ffff:192.0.2.128",
    "1::1.2.3.4",
    "1:2:3:4:5::1.2.3.4",
    "1:2:3:4::5:6:7",
    "2001:db8::8:800:200c:417a",
    "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210",
    "fe80::1234:5678",
    "2001:db8::",
    "2001:DB8:0:0:8:800:200C:417A",
    "1:2:3:4:5:6::7",
    "1:2::3:4:5:6:7",
]

IPV6_INVALID = [
    "",
    ":",
    ":::",
    "1",
    "1:2",
    "1:2:3:4:5:6:7",
    "1:2:3:4:5:6:7:8:9",
    "1::2::3",
    "12345::",
    "::12345",
    "::g",
    "1:::2",
    "1:2:3:4:5:6:7::8",
    "1::2:3:4:5:6:7:8",
    "::1.2.3",
    "::1.2.3.256",
    "::1.2.3.4:5",
    ":1:2:3:4:5:6:7",
    "1:2:3:4:5:6:7:",
    "[::1]",
]

URI_VALID = [
    "http://example.com/",
    "http://example.com",
    "http://user@example.com/",
    "http://user:pw@example.com:8080/x?q=1#f",
    "http://:@example.com/",
    "http://@example.com/",
    "http://%41@example.com/",
    "http://[::1]/",
    "http://[::1]:8080/path",
    "http://[::]/",
    "http://[1::]/",
    "http://[2001:db8::7]/c=GB?objectClass?one",
    "http://[v1.fe80::a+en1]/",
    "http://192.0.2.16:80/",
    "ftp://ftp.is.co.za/rfc/rfc1808.txt",
    "ldap://[2001:db8::7]/c=GB?objectClass?one",
    "mailto:John.Doe@example.com",
    "news:comp.infosystems.www.servers.unix",
    "tel:+1-816-555-1212",
    "telnet://192.0.2.16:80/",
    "urn:oasis:names:specification:docbook:dtd:xml:4.1.2",
    "mailto:",
    "urn:",
    "http:",
    "file:///etc/hosts",
    "http://example.com?a=b",
    "http://example.com#f",
    "foo:?a=b#f",
]

URI_INVALID = [
    "",
    "example.com/",
    "1http://example.com/",
    "http://[::1/",
    "http://[1::2::3]/",
    "http://[12345::]/",
    "http://exa mple.com/",
    "http://example.com/a b",
    "http://example.com/%zz",
    "http://example.com/%4",
    "http://example.com/a#b#c",
    "http://example.com/<>",
    "http://us er@example.com/",
    "http://a@b@example.com/",
    'http://example.com/"',
    "//example.com/",
    "?a=b",
    "#f",
]

REFERENCE_VALID = [
    "",
    "?a=b",
    "#f",
    "?a=b#f",
    "/",
    "/a/b",
    "a",
    "a/b",
    "../x",
    "./x:y",
    "//host",
    "//u@host/x",
    "//u:p@host/x",
    "//[::1]/x",
    "g;x?y#s",
]

REFERENCE_INVALID = [
    "a b",
    "a:b c",
    "//[::1",
    "1:2",
    "%zz",
    "a#b#c",
    "<a>",
]


class RFC3986GrammarTest(unittest.TestCase):
    def check(self, rule: str, valid: List[str], invalid: List[str]) -> None:
        for value in valid:
            with self.subTest(value=value):
                self.assertTrue(matches(rule, value), f"{value!r} should match")
        for value in invalid:
            with self.subTest(value=value):
                self.assertFalse(matches(rule, value), f"{value!r} should not match")

    def test_ipv6address(self) -> None:
        self.check(rfc3986.IPv6address, IPV6_VALID, IPV6_INVALID)

    def test_ip_literal(self) -> None:
        self.check(
            rfc3986.IP_literal,
            [f"[{v}]" for v in IPV6_VALID] + ["[v1.a]", "[vF.a:b]"],
            ["[]", "[v.a]", "[v1.]", "[::1", "::1]"],
        )

    def test_userinfo(self) -> None:
        self.check(
            rfc3986.userinfo,
            ["", "user", "user:pw", ":", "a%20b", "!$&'()*+,;=-._~"],
            ["a@b", "a b", "a/b", "%2"],
        )

    def test_uri(self) -> None:
        self.check(rfc3986.URI, URI_VALID[:-1] + ["foo:?a=b#f"], URI_INVALID)

    def test_absolute_uri(self) -> None:
        self.check(
            rfc3986.absolute_URI,
            ["http://user@example.com/", "mailto:", "foo:?a=b"],
            ["http://example.com/#f", "?a=b", ""],
        )

    def test_uri_reference(self) -> None:
        self.check(
            rfc3986.URI_reference,
            URI_VALID + REFERENCE_VALID,
            REFERENCE_INVALID + [v for v in URI_INVALID if v.startswith("http")],
        )

    def test_relative_ref(self) -> None:
        self.check(
            rfc3986.relative_ref,
            REFERENCE_VALID,
            ["http://[::1]/x#f", "a:b", "1:2"] + REFERENCE_INVALID[:3],
        )

    def test_host(self) -> None:
        self.check(
            rfc3986.host,
            ["example.com", "192.0.2.1", "[::1]", "[2001:db8::7]", "[v1.a]", "a%20b", ""],
            ["[::1", "a b", "a/b", "a@b"],
        )

    def test_path_empty(self) -> None:
        self.assertTrue(matches(rfc3986.path_empty, ""))
        self.assertFalse(matches(rfc3986.path_empty, "a"))


class RFC3986BacktrackingTest(unittest.TestCase):
    """Pathological non-matching inputs must fail in linear-ish time."""

    def test_no_catastrophic_backtracking(self) -> None:
        n = 20000
        cases: List[Tuple[str, str]] = [
            (rfc3986.URI_reference, "http://" + "a" * n + "!"),
            (rfc3986.URI_reference, "http://a/" + "a/" * n + "\x00"),
            (rfc3986.URI_reference, "http://a/?" + "a" * n + " "),
            (rfc3986.URI_reference, "http://[" + "1:" * n),
            (rfc3986.URI_reference, "http://[" + "1:" * 3 + ":" + "1:" * n + "x]"),
            (rfc3986.URI_reference, "http://" + "%41" * n + " "),
            (rfc3986.URI_reference, "//" + "a:" * n + "@@"),
            (rfc3986.URI_reference, "a" * n + " "),
            (rfc3986.URI, "http://" + "a" * n + "@" + "b" * n + " "),
        ]
        for rule, value in cases:
            with self.subTest(value=value[:20]):
                start = time.monotonic()
                matches(rule, value)
                self.assertLess(time.monotonic() - start, 2.0)


class HostIPv6Test(FieldTest[RequestLinterProtocol]):
    name = "Host"
    inputs = [b"[::1]:8080"]
    expected_out = "[::1]:8080"


class HostIPv6BareTest(FieldTest[RequestLinterProtocol]):
    name = "Host"
    inputs = [b"[2001:db8::7]"]
    expected_out = "[2001:db8::7]"


class HostBadIPv6Test(FieldTest[RequestLinterProtocol]):
    name = "Host"
    inputs = [b"[1::2::3]"]
    expected_out = "[1::2::3]"
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class OriginIPv6Test(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"http://[::1]:8080"]
    expected_out: Optional[OriginValue] = OriginValue("http", "[::1]", 8080)


class OriginIPv6EmptyTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"https://[::]"]
    expected_out = OriginValue("https", "[::]", None)


class OriginUserinfoTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"http://user@example.com"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_ORIGIN_SYNTAX]


class OriginBadIPv6Test(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"http://[1::2::3]"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_ORIGIN_SYNTAX]


if __name__ == "__main__":
    unittest.main()
