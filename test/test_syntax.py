import importlib
import itertools
import re
import sys
import time
import unittest
from functools import partial
from typing import Any, Callable, Iterator, List, Sequence, Tuple, Type

from httplint import HttpRequestLinter, HttpResponseLinter, syntax
from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED, HttpField
from httplint.field.broken_field import BrokenField
from httplint.field.list_field import HttpListField
from httplint.field.parsers.link import LINK_BAD_TARGET_URI
from httplint.field.parsers.location import LOCATION_BAD_URI, LOCATION_NOT_ABSOLUTE
from httplint.field.parsers.referer import REFERER_BAD_URI
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FakeResponseLinter
from httplint.note import Note, categories, levels
from httplint.syntax import (
    rfc3986,
    rfc5322,
    rfc5646,
    rfc5987,
    rfc8288,
    rfc9110,
    rfc9112,
    rfc9651,
)
from httplint.types import AddNoteMethodType, ResponseLinterProtocol
from httplint.util import invalid_char_problem


def check_regex() -> None:
    """Grab all the regex in this module."""
    modules = 0
    count = 0
    errors = 0
    for module_name in syntax.__all__:
        modules += 1
        full_name = f"httplint.syntax.{module_name}"
        importlib.import_module(full_name)
        module = sys.modules[full_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, str):
                count += 1
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error as why:
                    errors += 1
                    print("*", module_name, attr_name, why)
    return count, modules, errors


TIME_LIMIT = 1.0  # seconds; the unfixed grammars take many seconds on these inputs
SEMIS = "; " * 24  # the parameters grammar doubled its work for each ";"


def lint_request(name: bytes, value: bytes) -> None:
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
    linter.process_headers([(name, value)])
    linter.finish_content(True)


def lint_response(name: bytes, value: bytes) -> None:
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(name, value)])
    linter.finish_content(True)


def field_notes(response: bool, name: bytes, value: bytes) -> List[str]:
    "The names of the notes that one field line produces."
    if response:
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    else:
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
    linter.process_headers([(name, value)])
    linter.finish_content(True)
    return [type(note).__name__ for note in linter.notes]


def lint_target(target: bytes) -> None:
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", target, b"HTTP/1.1")
    linter.finish_content(True)


class SyntaxBacktrackingTest(unittest.TestCase):
    """Pathological non-matching inputs must fail in bounded time."""

    def check(self, label: str, func: Callable[..., None], *args: bytes) -> None:
        with self.subTest(label):
            start = time.monotonic()
            func(*args)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{label}: {elapsed:.2f}s")

    def test_parameters(self) -> None:
        bad = SEMIS.encode() + b"\x80"
        cases: List[Tuple[str, bool, bytes, bytes]] = [
            ("Content-Type", False, b"Content-Type", b"text/plain" + bad),
            ("Content-Type response", True, b"Content-Type", b"text/plain" + bad),
            ("Accept", False, b"Accept", b"text/plain" + bad),
            ("Accept-Post", True, b"Accept-Post", b"text/plain" + bad),
            ("Accept-Patch", True, b"Accept-Patch", b"text/plain" + bad),
            ("Expect", False, b"Expect", b"a=b" + bad),
            ("Server-Timing", True, b"Server-Timing", b"a" + bad),
            (
                "Link type",
                True,
                b"Link",
                b'<http://a/>; type="text/plain' + SEMIS.encode() + b'\x80"',
            ),
        ]
        for label, response, name, value in cases:
            lint = lint_response if response else lint_request
            self.check(label, lint, name, value)

    def test_range(self) -> None:
        value = b"bytes=" + b",".join([b"0-1"] * 24) + b",\x7f"
        self.check("Range", lint_request, b"Range", value)

    def test_partial_uri(self) -> None:
        value = b"a" * 15000 + b"<"
        self.check("Content-Location", lint_response, b"Content-Location", value)
        self.check("Referer", lint_request, b"Referer", value)

    def test_origin_form(self) -> None:
        self.check("request target", lint_target, b"/" + b"a" * 15000 + b"%zz")

    def check_rule(self, label: str, rule: str, value: str) -> None:
        "Match a rule that no field uses, as a field would (with its padding and flags)."
        compiled = re.compile(rf"^\s*(?:{rule})\s*$", re.VERBOSE | re.IGNORECASE)
        with self.subTest(label):
            start = time.monotonic()
            compiled.match(value)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{label}: {elapsed:.2f}s")

    def check_full(self, label: str, rule: str, value: str) -> None:
        "Match a rule that isn't padded when it is used (a start-line or a message)."
        compiled = re.compile(rule, re.VERBOSE | re.IGNORECASE)
        with self.subTest(label):
            start = time.monotonic()
            compiled.fullmatch(value)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, TIME_LIMIT, f"{label}: {elapsed:.2f}s")

    def test_translation_rules(self) -> None:
        """
        Guards for the rules rewritten for #239: the obvious ways to write link-param,
        field-value and received-by (and an unrolled comment) backtrack badly, and the
        rules are written to avoid that. They pass on main as well.
        """
        a_comment = b"1.1 a (x (y (z)))"
        link = b"</a>"
        cases = [
            ("Link BWS", True, b"Link", link + b"; a " * 24 + b"\x80"),
            ("Link BWS tight", True, b"Link", link + b" ;a" * 24 + b"\x80"),
            ("Link BWS long", True, b"Link", link + b"; a " * 2000 + b"\x80"),
            ("Via comments", True, b"Via", b", ".join([a_comment] * 24) + b"\x80"),
            ("Via long comment", True, b"Via", b"1.1 a (((" + b"a" * 5000 + b"))))" + b"\x80"),
            ("Via host", True, b"Via", b"1.1 " + b"a#b:80, " * 24 + b"\x80"),
            ("From comment", False, b"From", b"(" + b"a|b" * 3000 + b") \x80"),
        ]
        for label, response, name, value in cases:
            lint = lint_response if response else lint_request
            self.check(label, lint, name, value)
        for label, unit in [
            ("host:port", "1.1 a:80, "),
            ("host", "1.1 a, "),
            ("IP literal", "1.1 [::1]:80, "),
            ("host:port comment", "1.1 a.b:80 (x (y)), "),
        ]:
            self.check_rule(f"Via {label}", rfc9110.Via, unit * 24 + "\x01")
            self.check_rule(f"Via {label} long", rfc9110.Via, unit * 2000 + "\x01")
        self.check_rule("field-line", rfc9112.field_line, "A: " + "a b " * 2000 + "\x01")
        self.check_rule("field-value", rfc9110.field_value, "a b " * 2000 + "\x01")
        self.check_rule("field-value words", rfc9110.field_value, "aaa " * 24 + "\x01")
        self.check_rule("field-value long words", rfc9110.field_value, "aaa " * 2000 + "\x01")
        self.check_rule("field-value tabs", rfc9110.field_value, "a \t" * 2000 + "\x01")
        self.check_rule("chunk-ext", rfc9112.chunk_ext, "; a " * 2000 + "\x80")
        self.check_rule("ext-value", rfc5987.ext_value, "UTF-8''" + "a" * 15000 + "\x80")
        self.check_rule(
            "ext-value language", rfc5987.ext_value, "UTF-8'" + "en-abcde" * 1500 + "'\x80"
        )

    def test_transfer_encoding(self) -> None:
        """
        The RFC 7230 transfer-coding listed chunked, compress, deflate and gzip before
        transfer-extension, so each of them matched by two routes: 2**n paths for n elements.
        """
        for name in ["gzip", "chunked", "a;b=c"]:
            self.check_rule(
                f"Transfer-Encoding {name}",
                str(rfc9112.Transfer_Encoding),
                ", ".join([name] * 24) + "\x80",
            )

    def test_start_line_rules(self) -> None:
        """
        Guard: the RFC 9112 start-line rules match long non-matching input in linear time. They
        are not used to match messages, but they are transcriptions that someone may use.
        """
        n = 15000
        bad = "\x01"
        cases = [
            ("authority-form host", rfc9112.authority_form, "a" * n + bad),
            ("authority-form pct", rfc9112.authority_form, "%41" * n + bad),
            ("authority-form dots", rfc9112.authority_form, "1." * n + bad),
            ("authority-form port", rfc9112.authority_form, "a:" + "1" * n + bad),
            ("authority-form IPv6", rfc9112.authority_form, "[" + "1:" * n + "]" + bad),
            ("request-line origin", rfc9112.request_line, "GET /" + "a/" * n + " " + bad),
            ("request-line query", rfc9112.request_line, "GET /?" + "a/?" * n + " " + bad),
            ("request-line absolute", rfc9112.request_line, "GET http://" + "a." * n + " " + bad),
            ("request-line path", rfc9112.request_line, "GET http://a" + "/a" * n + " " + bad),
            ("request-line authority", rfc9112.request_line, "CONNECT " + "a" * n + bad),
            ("request-line method", rfc9112.request_line, "G" * n + bad),
            ("request-line spaces", rfc9112.request_line, "GET " + "/ " * n + bad),
            ("status-line reason", rfc9112.status_line, "HTTP/1.1 200 " + "a b\t" * n + bad),
            ("status-line obs-text", rfc9112.status_line, "HTTP/1.1 200 " + "\x80" * n + bad),
            ("status-line spaces", rfc9112.status_line, "HTTP/1.1 200" + " " * n + bad),
            ("reason-phrase", rfc9112.reason_phrase, "a b" * n + bad),
            ("start-line", rfc9112.start_line, "HTTP/1.1 200 " + "a " * n + bad),
            ("HTTP-version", rfc9112.HTTP_version, "HTTP/1." + "1" * n),
        ]
        for label, rule, value in cases:
            self.check_full(label, rule, value)
        message = "GET / HTTP/1.1\r\n"
        for label, value in [
            ("HTTP-message fields", message + "A: b\r\n" * 2000 + bad),
            ("HTTP-message long value", message + "A: " + "a b " * 2000 + bad),
            ("HTTP-message name", message + "A" * n + bad),
            ("HTTP-message start", "GET /" + "a/" * n + bad),
            ("HTTP-message folds", message + "A: b\r\n" + " c\r\n" * 2000 + bad),
        ]:
            self.check_full(label, rfc9112.HTTP_message, value)

    def test_language_tag(self) -> None:
        "Guard: these rules were dead before the alphanum fix, so main is fast on them too."
        n = 1500
        bad = b"\x80"
        cases = [
            ("variants", b"en" + b"-abcde" * n + bad),
            ("short variants", b"en" + b"-1abc" * n + bad),
            ("extensions", b"en" + b"-a-bb" * n + bad),
            ("long extensions", b"en" + b"-a-bbbbbbbb-c" * n + bad),
            ("private use", b"en-x" + b"-abcdefgh" * n + bad),
            ("extlang", b"en" + b"-abc" * n + bad),
            ("list", b", ".join([b"en-x-a"] * n) + bad),
        ]
        for label, value in cases:
            self.check(f"Content-Language {label}", lint_response, b"Content-Language", value)


def matches(rule: str, value: str) -> bool:
    return re.match(rf"^\s*(?:{rule})\s*$", value, re.VERBOSE | re.IGNORECASE) is not None


class SyntaxAcceptRejectTest(unittest.TestCase):
    """The backtracking rewrites must accept and reject what they did before."""

    def check(self, rule: str, accepted: List[str], rejected: List[str]) -> None:
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(matches(rule, value))
        for value in rejected:
            with self.subTest(value=value):
                self.assertFalse(matches(rule, value))

    def test_parameters(self) -> None:
        self.check(
            rfc9110.media_type,
            [
                "text/plain",
                "text/plain;",
                "text/plain; ;",
                "text/plain; ; a=b",
                "text/plain;a=b",
                "text/plain ; a=b ;c=d",
                'text/plain; a="x\\"y"',
                'text/plain; a="b;c"; ; d=e',
                "text/plain \t;\t",
            ],
            [
                "text/plain; a",
                "text/plain; a=",
                "text/plain; =b",
                "text/plain a=b",
                'text/plain; a="x',
                'text/plain; a="x\\"',
                "text/plain; a=b c=d",
                "text/plain; ; \x80",
            ],
        )
        self.check(
            rfc9110.expectation,
            ["100-continue", "a=b; ;c=d", 'a="b"; c="d\\"e"'],
            ["a=b; c", 'a="b', "a=b ; ; c="],
        )

    def test_range(self) -> None:
        self.check(
            rfc9110.Range,
            ["bytes=0-1", "bytes=0-", "bytes=-1", "bytes=0-1,-1", "bytes=0-1, 2-3", "bytes=a"],
            ["bytes=", "bytes=0-1,", "bytes=0 -1", "bytes=0-1,\x7f", "0-1"],
        )

    def test_origin_form(self) -> None:
        self.check(
            rfc9112.origin_form,
            ["/", "/a/b", "//x", "/a?", "/a?b=c", "/a?b/c?d", "/a??"],
            ["a", "?a", "/a b", "/a#b", "/a?b c", "/%zz", "/a?%zz"],
        )

    def test_partial_uri(self) -> None:
        self.check(
            rfc9110.partial_URI,
            ["", "a", "/a", "a/b:c", "./a:b", "/a?b=c", "a?b:c", "//host/p?q"],
            ["1:2", "a:b", "//a:a b", "a b"],
        )


class SyntaxCaseSensitiveTest(unittest.TestCase):
    """
    Fields match with re.IGNORECASE; %x literals in the ABNF are case-sensitive.

    The old rule is the new one with its (?-i: ... ) groups made ordinary groups, so every
    difference between them has to be a case variant that the new rule rejects.
    """

    def old(self, rule: str) -> str:
        self.assertIn("(?-i:", rule)
        return rule.replace("(?-i:", "(?:")

    def check(self, rule: str, value: str, mutable: str = "") -> None:
        """
        The old rule accepts every case variant of `value`; the new one accepts `value`, and
        only the variants whose changed letter falls inside `mutable` (the part that isn't a
        case-sensitive literal).
        """
        old = self.old(rule)
        self.assertTrue(matches(rule, value))
        for i, char in enumerate(value):
            if not char.isalpha():
                continue
            variant = value[:i] + char.swapcase() + value[i + 1 :]
            with self.subTest(variant=variant):
                self.assertTrue(matches(old, variant))
                in_mutable = mutable != "" and value.find(mutable) <= i < value.find(mutable) + len(
                    mutable
                )
                self.assertEqual(matches(rule, variant), in_mutable)
        for variant in (value.lower(), value.upper()):
            with self.subTest(variant=variant):
                self.assertTrue(matches(old, variant))
                if variant != value and not mutable:
                    self.assertFalse(matches(rule, variant))

    def test_http_date(self) -> None:
        for value in [
            "Mon, 01 Jan 2000 00:00:00 GMT",
            "Monday, 01-Jan-00 00:00:00 GMT",
            "Mon Jan  1 00:00:00 2000",
            "Sun, 31 Dec 1999 23:59:59 GMT",
        ]:
            with self.subTest(value=value):
                self.check(rfc9110.HTTP_date, value)

    def test_http_date_rejects_lower_case(self) -> None:
        for value in [
            "mon, 01 jan 2000 00:00:00 gmt",
            "Mon, 01 Jan 2000 00:00:00 gmt",
            "Mon, 01 jan 2000 00:00:00 GMT",
            "mon, 01 Jan 2000 00:00:00 GMT",
            "MON, 01 JAN 2000 00:00:00 GMT",
            "monday, 01-jan-00 00:00:00 GMT",
            "mon jan  1 00:00:00 2000",
        ]:
            with self.subTest(value=value):
                self.assertFalse(matches(rfc9110.HTTP_date, value))

    def test_entity_tag(self) -> None:
        # The opaque tag is case-insensitive here only because etagc accepts both cases.
        self.check(rfc9110.entity_tag, 'W/"foo"', mutable='"foo"')
        self.check(rfc9110.ETag, 'W/"Foo"', mutable='"Foo"')
        self.assertTrue(matches(rfc9110.entity_tag, '"foo"'))
        self.assertTrue(matches(rfc9110.entity_tag, '"w/foo"'))
        self.assertFalse(matches(rfc9110.entity_tag, 'w/"foo"'))
        self.assertFalse(matches(rfc9110.If_None_Match, 'w/"foo"'))
        self.assertFalse(matches(rfc9110.If_None_Match, '"a", w/"foo"'))
        self.assertTrue(matches(rfc9110.If_None_Match, '"a", W/"foo"'))
        self.assertFalse(matches(rfc9110.If_Range, 'w/"foo"'))

    def test_http_name(self) -> None:
        self.check(rfc9112.HTTP_name, "HTTP")
        self.assertFalse(matches(rfc9112.HTTP_name, "http"))

    def test_structured_field_key(self) -> None:
        for value in ["a", "*a", "a-b.c_d*", "a1"]:
            with self.subTest(value=value):
                self.assertTrue(matches(rfc9651.key, value))
        for value in ["A", "Foo", "fOo", "*A", "a-B"]:
            with self.subTest(value=value):
                self.assertFalse(matches(rfc9651.key, value))
        self.assertFalse(matches(rfc9651.sf_dictionary, "Foo=1"))
        self.assertTrue(matches(rfc9651.sf_dictionary, "foo=1, bar=Baz"))
        self.assertFalse(matches(rfc9651.sf_item, "a;Foo=1"))


class SyntaxLanguageTagTest(unittest.TestCase):
    "rfc5646.alphanum was missing its f-string prefix (issue #238)."

    old_alphanum = r"(?: {ALPHA} | {DIGIT} )"  # literal text, as it was

    def old_language_tag(self) -> str:
        "Language-Tag as it was built before the fix."
        self.assertNotEqual(rfc5646.alphanum, self.old_alphanum)
        alphanum = self.old_alphanum
        digit = rfc5646.DIGIT
        variant = rf"(?: {alphanum}{{5,8}} | (?: {digit} {alphanum}{{3}} ) )"
        extension = rf"{rfc5646.singleton} (?: \- {alphanum}{{2,8}} ){{1,}}"
        privateuse = rf"x (?: \- {alphanum}{{1,8}} ){{1,}}"
        return rf"""(?: (?:
            {rfc5646.language}
            (?: \- {rfc5646.script} )?
            (?: \- {rfc5646.region} )?
            (?: \- {variant} )*
            (?: \- {extension} )*
            (?: \- {privateuse} )?
        ) | {privateuse} | {rfc5646.grandfathered} )"""

    def test_accepts_extended_tags(self) -> None:
        for value in [
            "en-x-foo",
            "de-CH-1996",
            "x-foo",
            "sl-rozaj",
            "sl-rozaj-biske",
            "en-u-ca-gregory",
            "zh-Hant-x-private",
            "de-CH-x-phonebk",
            "az-Arab-x-AZE-derbend",
            "hy-Latn-IT-arevela",
            "de-DE-u-co-phonebk",
            "en-a-bbb-x-a-ccc",
            "qaa-Qaaa-QM-x-southern",
            "zh-yue-HK",
            "x-abcdefgh",
        ]:
            with self.subTest(value=value):
                self.assertTrue(matches(rfc5646.Language_Tag, value))

    def test_rejects(self) -> None:
        for value in [
            "x-{ALPHA}",
            "en-{ALPHA}{ALPHA}{ALPHA}{ALPHA}{ALPHA}",
            "en-x-{DIGIT}",
            "de-419-DE",
            "a-DE",
            "en-",
            "-en",
            "en-x",
            "en-a",
            "en-x-abcdefghi",
            "en-abcdefghi",
            "en--US",
        ]:
            with self.subTest(value=value):
                self.assertFalse(matches(rfc5646.Language_Tag, value))

    def test_differential(self) -> None:
        "Everything the old rule accepted is still accepted; the new ones are extended tags."
        old = self.old_language_tag()
        subtags = ["en", "de", "Latn", "CH", "419", "1996", "x", "u", "ca", "foo", "rozaj"]
        subtags.append("abcdefghi")
        newly_accepted = 0
        for count in range(1, 5):
            for combo in itertools.product(subtags, repeat=count):
                value = "-".join(combo)
                was, now = matches(old, value), matches(rfc5646.Language_Tag, value)
                with self.subTest(value=value):
                    if was:
                        self.assertTrue(now)
                    elif now:
                        newly_accepted += 1
                        # It needs a variant, extension or private-use subtag to be new.
                        self.assertTrue(
                            any(
                                len(sub) == 1
                                or 5 <= len(sub) <= 8
                                or (len(sub) == 4 and sub[0].isdigit())
                                for sub in combo
                            ),
                            value,
                        )
        self.assertGreater(newly_accepted, 100)


def fullmatch(rule: str, value: str) -> bool:
    "Like matches(), but without the whitespace padding."
    return re.fullmatch(rule, value, re.VERBOSE | re.IGNORECASE) is not None


def strings(alphabet: Sequence[str], max_length: int) -> Iterator[str]:
    "Every string over the alphabet, up to max_length."
    for length in range(max_length + 1):
        for combo in itertools.product(alphabet, repeat=length):
            yield "".join(combo)


class SyntaxTranslationTest(unittest.TestCase):
    """
    ABNF translation errors in the syntax modules (issue #239).

    Each rule is compared with its old text over short strings, so that the only differences
    are the deliberate ones.
    """

    def test_comment_text_chars(self) -> None:
        "rfc5322 ctext is %d33-39 / %d42-91 / %d93-126; it had lost the end of the last range."
        old = rfc5322.ctext.replace(r"\x5d-\x7e", r"\x5d\x7e")
        self.assertNotEqual(old, rfc5322.ctext)
        for code in range(256):
            char = chr(code)
            with self.subTest(char=repr(char)):
                was, now = fullmatch(old, char), fullmatch(rfc5322.ctext, char)
                self.assertEqual(was, now and char not in "^_`{|}")
                self.assertEqual(now, 33 <= code <= 39 or 42 <= code <= 91 or 93 <= code <= 126)

    def test_comment_text_in_from(self) -> None:
        for value in ["(a_b) w@x.org", "(a|b) w@x.org", "(a^b) w@x.org", "(a~b{c}) w@x.org"]:
            with self.subTest(value=value):
                self.assertTrue(matches(rfc9110.From, value))
        for value in ["(a(b) w@x.org", "(a\\) w@x.org", "(a) b w@x.org"]:
            with self.subTest(value=value):
                self.assertFalse(matches(rfc9110.From, value))
        for value in [b"(a_b) w@x.org", b"(a|b) w@x.org", b"(a^b) w@x.org"]:
            with self.subTest(value=value):
                self.assertNotIn("BAD_SYNTAX", field_notes(False, b"From", value))

    def test_rfc5987_hash(self) -> None:
        "An unescaped # starts a comment under re.VERBOSE, which dropped the rest of the line."
        for old_form, new, lost in [
            (rfc5987.attr_char.replace(r"\#", "#"), rfc5987.attr_char, "#$&+-."),
            (rfc5987.mime_charsetc.replace(r"\#", "#"), rfc5987.mime_charsetc, "#$%&"),
        ]:
            self.assertNotEqual(old_form, new)
            for code in range(256):
                char = chr(code)
                with self.subTest(char=repr(char)):
                    was, now = fullmatch(old_form, char), fullmatch(new, char)
                    self.assertEqual(was, now and char not in lost)
        for value in ["UTF-8''foo-bar", "UTF-8''a.b", "UTF-8''a+b", "UTF-8'en'a%20b#$&", "ab''x"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc5987.ext_value, value))
        for value in ["UTF-8'foo", "UTF-8''a b", "UTF-8''a*b", "UTF-8''a%zz", "UTF-8''a'b"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc5987.ext_value, value))

    def test_link_param_bws(self) -> None:
        token, quoted_string = rfc9110.token, rfc9110.quoted_string
        old_param = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"
        old_value = (
            rf"(?: < {rfc3986.URI_reference} > (?: {rfc9110.OWS} ; {rfc9110.OWS} {old_param} )* )"
        )
        for old, new, prefix in [
            (old_param, rfc8288.link_param, ""),
            (old_value, rfc8288.link_value, "<a>;"),
        ]:
            for tail in strings(["a", "=", " ", '"', ";"], 6):
                value = prefix + tail
                with self.subTest(value=value):
                    was, now = fullmatch(old, value), fullmatch(new, value)
                    # The new rule differs only by allowing whitespace around "=".
                    self.assertEqual(now, fullmatch(old, re.sub(r"[ \t]*=[ \t]*", "=", value)))
                    if was != now:
                        self.assertTrue(now)
                        self.assertRegex(value, r"[ \t]=|=[ \t]")
        for value in ['<a>; rel = "next"', "<a>; rel =next", "<a>; rel= next", "<a> ;a ;b = c ;d"]:
            with self.subTest(value=value):
                self.assertTrue(matches(rfc8288.Link, value))
                self.assertFalse(matches(old_value, value))
        for value in ["<a>; rel = ", "<a>; = next", '<a>; rel "next"']:
            with self.subTest(value=value):
                self.assertFalse(matches(rfc8288.Link, value))
        self.assertNotIn("BAD_SYNTAX_DETAILED", field_notes(True, b"Link", b'</a>; rel = "next"'))
        self.assertNotIn("BAD_SYNTAX", field_notes(True, b"Link", b'</a>; rel = "next"'))

    def test_field_content(self) -> None:
        def vchar(char: str) -> bool:
            return "\x21" <= char <= "\x7e" or char >= "\x80"

        def reference_value(value: str) -> bool:
            "Empty, or SP, HTAB and field-vchar that starts and ends with a field-vchar."
            if not value:
                return True
            return (
                vchar(value[0]) and vchar(value[-1]) and all(vchar(c) or c in " \t" for c in value)
            )

        sp_htab = rf"(?: {rfc9110.SP} | {rfc9110.HTAB} )"
        old_content = rf"(?: {rfc9110.field_vchar} (?: {sp_htab}+ {rfc9110.field_vchar} )? )"
        old_value = rf"(?: {old_content} )*"
        for value in strings(["a", "b", " ", "\t", "\x01", "\x80"], 6):
            with self.subTest(value=repr(value)):
                now = fullmatch(rfc9110.field_value, value)
                self.assertEqual(now, reference_value(value))
                if fullmatch(old_value, value):
                    self.assertTrue(now)
                # field-content alone is a single field-vchar, or three or more characters.
                self.assertEqual(
                    fullmatch(rfc9110.field_content, value),
                    reference_value(value) and value != "" and len(value) != 2,
                )
        self.assertFalse(fullmatch(old_value, "a a a"))
        for value in ["a a a", "a  b\tc d", "a b c d e"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9110.field_value, value))
                self.assertTrue(fullmatch(rfc9112.field_line, f"A: {value}"))

    def test_received_by(self) -> None:
        host, port = rfc9110.uri_host, rfc9110.port
        old = rf"(?: (?: {host} (?: : {port} )? ) | {rfc9110.pseudonym} )"
        for value in strings(["a", "1", "#", ":", "[", "]", "(", "=", ".", "%"], 5):
            with self.subTest(value=value):
                was, now = fullmatch(old, value), fullmatch(rfc9110.received_by, value)
                if was and not now:
                    # RFC 9110 has no empty received-by, and a pseudonym is a token: no "(" or "=".
                    self.assertTrue(value == "" or value[0] == ":" or "(" in value or "=" in value)
                elif now and not was:
                    # A token that isn't a host has a character that a host can't have.
                    self.assertTrue(any(c in value for c in "#%"), value)
        for value in ["a#b:80", "a#b", "a^b", "example.org:8080", "[::1]:80", "[::1]", "a:"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9110.received_by, value))
        for value in ["a:b", "a b", "a#b:c", "", ":80", "a(b)", "a=b", "a,b", "a;b", "[::1", "[a]"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9110.received_by, value))
        # What the old rule accepted that RFC 9110 doesn't, and the new one rejects.
        for value in ["", ":80", "a(b)", "a=b", "a;b", "a,b"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(old, value))
        self.assertTrue(matches(rfc9110.Via, "1.1 a#b:80 (a comment), 1.0 [::1]"))
        self.assertFalse(matches(rfc9110.Via, "1.1 :80"))
        self.assertNotIn("BAD_SYNTAX_DETAILED", field_notes(True, b"Via", b"1.1 a#b:80"))

    def test_transfer_encoding_list(self) -> None:
        old = str(rfc9110.list_rule(rfc9112.transfer_coding, 1))
        new = str(rfc9112.Transfer_Encoding)
        for value in strings(["gzip", ",", " ", ";", "a=b"], 5):
            with self.subTest(value=value):
                was, now = matches(old, value), matches(new, value)
                if was != now:
                    self.assertEqual((was, now, value.strip()), (False, True, ""))
        self.assertTrue(matches(new, ""))
        self.assertTrue(matches(new, "gzip, chunked"))
        self.assertFalse(matches(new, "gzip,"))

    def test_transfer_coding_is_rfc9110(self) -> None:
        "RFC 9112 imports transfer-coding; the RFC 7230 form accepted the same language."
        self.assertIs(rfc9112.transfer_coding, rfc9110.transfer_coding)
        for name in ["transfer_parameter", "transfer_extension"]:
            self.assertFalse(hasattr(rfc9112, name))
        param = rf"(?: {rfc9110.token} {rfc9110.BWS} = {rfc9110.BWS} (?: {rfc9110.token} | {rfc9110.quoted_string} ) )"
        extension = rf"(?: {rfc9110.token} (?: {rfc9110.OWS} ; {rfc9110.OWS} {param} )* )"
        old = rf"(?: chunked | compress | deflate | gzip | {extension} )"
        old_list = str(rfc9110.list_rule(old))
        for value in strings(["gzip", "chunked", "a", " ", ";", "=", '"', ","], 5):
            with self.subTest(value=value):
                self.assertEqual(
                    fullmatch(old, value), fullmatch(rfc9112.transfer_coding, value), value
                )
                self.assertEqual(
                    matches(old_list, value), matches(str(rfc9112.Transfer_Encoding), value), value
                )
        for value in ["gzip", "Chunked", "gzip;a=b", 'x;a="b c" ; d=e', "x-gzip"]:
            self.assertTrue(fullmatch(rfc9112.transfer_coding, value))
        for value in ["", "gzip;", "gzip;a", "a b", "gzip,chunked"]:
            self.assertFalse(fullmatch(rfc9112.transfer_coding, value))

    # The rules as they were: authority-form = authority, and a CRLF on the request-line.
    OLD_REQUEST_TARGET = (
        rf"(?: {rfc9112.origin_form} | {rfc9112.absolute_form} | {rfc3986.authority} "
        rf"| {rfc9112.asterisk_form} )"
    )
    OLD_REQUEST_LINE = (
        rf"(?: {rfc9112.method} [ ] {OLD_REQUEST_TARGET} [ ] {rfc9112.HTTP_version} "
        rf"{rfc9112.CRLF} )"
    )
    OLD_REASON_PHRASE = (
        rf"(?: {rfc9112.HTAB} | {rfc9112.SP} | {rfc9112.VCHAR} | {rfc9112.obs_text} )*"
    )
    OLD_STATUS_LINE = (
        rf"(?: {rfc9112.HTTP_version} [ ] {rfc9112.status_code} [ ] {OLD_REASON_PHRASE} "
        rf"{rfc9112.CRLF} )"
    )

    def test_authority_form(self) -> None:
        "authority-form is uri-host ':' port (RFC 9112 Section 3.2.3), not authority."

        def reference(value: str) -> bool:
            "A host, then the last ':', then DIGITs (possibly none, as in RFC 3986's port)."
            host, colon, port = value.rpartition(":")
            return (
                bool(colon)
                and re.fullmatch("[0-9]*", port) is not None
                and fullmatch(rfc3986.host, host)
            )

        for value in strings(["a", "1", ":", "@", "[", "]", "."], 6):
            with self.subTest(value=value):
                now = fullmatch(rfc9112.authority_form, value)
                self.assertEqual(now, reference(value))
                # Narrower than authority: nothing new is accepted.
                if now:
                    self.assertTrue(fullmatch(rfc3986.authority, value))
        # An empty host (reg-name = *( ... )) and an empty port (port = *DIGIT) are valid ABNF.
        for value in ["example.org:80", "a:", ":80", ":", "[::1]:443", "1.2.3.4:8080", "a%41:1"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.authority_form, value))
        # What authority accepted and authority-form rejects: no port, or userinfo.
        for value in ["example.org", "[::1]", "u@example.org:80", "u:p@example.org", ""]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc3986.authority, value))
                self.assertFalse(fullmatch(rfc9112.authority_form, value))
        for value in ["a:b", "a:80:80", "a b:80", "[::1:80", "a:80 ", "a@b:80"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.authority_form, value))

    def test_request_target(self) -> None:
        "Only the authority-form change reaches request-target and request-line."
        old_authority = rfc3986.authority
        old_target = self.OLD_REQUEST_TARGET
        old_line = self.OLD_REQUEST_LINE
        for target in strings(["a", "1", ":", "@", "/", "?", "*", "[", "]"], 5):
            with self.subTest(target=target):
                was = fullmatch(old_target, target)
                now = fullmatch(rfc9112.request_target, target)
                if was != now:
                    # authority-form lost the forms without a port, and userinfo.
                    self.assertEqual((was, now), (True, False))
                    self.assertTrue(fullmatch(old_authority, target))
                    self.assertFalse(fullmatch(rfc9112.authority_form, target))
                # The request-line differs only through its request-target, and loses its CRLF.
                line = f"GET {target} HTTP/1.1"
                self.assertEqual(fullmatch(old_line, line + "\r\n"), was)
                self.assertEqual(fullmatch(rfc9112.request_line, line), now)
        for line in ["GET / HTTP/1.1", "OPTIONS * HTTP/1.1", "CONNECT a.example:443 HTTP/1.1"]:
            self.assertTrue(fullmatch(rfc9112.request_line, line))
            self.assertFalse(fullmatch(rfc9112.request_line, line + "\r\n"))
        for line in ["CONNECT a.example HTTP/1.1", "GET  / HTTP/1.1", "GET /  HTTP/1.1"]:
            self.assertFalse(fullmatch(rfc9112.request_line, line))

    def test_status_line(self) -> None:
        "status-line loses its CRLF, and reason-phrase is 1*( ... ) inside [ ]."
        old_reason, old = self.OLD_REASON_PHRASE, self.OLD_STATUS_LINE
        pieces = ["HTTP/1.1", " ", "200", "OK", "\t", "\x80", "\x7f", "\x01", "\r\n", "\n"]
        for value in strings(pieces, 5):
            with self.subTest(value=value):
                self.assertEqual(
                    fullmatch(old, value + "\r\n"), fullmatch(rfc9112.status_line, value), value
                )
        for value in ["HTTP/1.1 200 OK", "HTTP/1.1 200 ", "HTTP/1.1 404 Not\tFound \x80", "HTTP/1.0 200 a"]:
            self.assertTrue(fullmatch(rfc9112.status_line, value))
        # The space after the status code is required even when there is no reason-phrase.
        for value in ["HTTP/1.1 200", "HTTP/1.1 20 OK", "HTTP/1.1 200 OK\r\n", "HTTP/1.1 200 \x01"]:
            self.assertFalse(fullmatch(rfc9112.status_line, value))
        # The rule alone no longer matches nothing: that is what [ ] is for.
        self.assertTrue(fullmatch(old_reason, ""))
        self.assertFalse(fullmatch(rfc9112.reason_phrase, ""))
        for value in ["a", " ", "\t", "\x80", "a b\tc"]:
            self.assertTrue(fullmatch(rfc9112.reason_phrase, value))
        for value in ["\x01", "a\r\nb", "a\x7f"]:
            self.assertFalse(fullmatch(rfc9112.reason_phrase, value))

    def test_http_message(self) -> None:
        "HTTP-message puts the CRLF after start-line, as RFC 9112 Section 2.1 does."
        old_start = rf"(?: {self.OLD_REQUEST_LINE} | {self.OLD_STATUS_LINE} )"
        old = rf"(?: {old_start} (?: {rfc9112.field_line} {rfc9112.CRLF} )* {rfc9112.CRLF} (?: {rfc9112.message_body} )? )"
        pieces = ["GET / HTTP/1.1", "HTTP/1.1 200 OK", "\r\n", "A: b", "A:", " c", "\n"]
        count = 0
        for value in strings(pieces, 5):
            with self.subTest(value=value):
                now = fullmatch(rfc9112.HTTP_message, value)
                self.assertEqual(fullmatch(old, value), now, value)
                count += now
        self.assertGreater(count, 100)
        for value in [
            "GET / HTTP/1.1\r\n\r\n",
            "GET / HTTP/1.1\r\nHost: a\r\nA:\r\n\r\nbody\r\n",
            "HTTP/1.1 200 \r\nA: b\r\n\r\n",
            "HTTP/1.1 200 OK\r\n\r\n\x00\xff",
        ]:
            self.assertTrue(fullmatch(rfc9112.HTTP_message, value))
        for value in ["GET / HTTP/1.1\r\n", "GET / HTTP/1.1\r\n\r", "GET / HTTP/1.1\r\n A\r\n\r\n", "\r\n\r\n"]:
            self.assertFalse(fullmatch(rfc9112.HTTP_message, value))
        # The one change in language is the authority-form's, via request-target.
        old_message = rf"(?: {self.OLD_REQUEST_LINE} (?: {rfc9112.field_line} {rfc9112.CRLF} )* {rfc9112.CRLF} (?: {rfc9112.message_body} )? )"
        self.assertTrue(fullmatch(rfc9112.HTTP_message, "CONNECT a:80 HTTP/1.1\r\n\r\n"))
        self.assertTrue(fullmatch(old_message, "CONNECT a:80 HTTP/1.1\r\n\r\n"))
        self.assertFalse(fullmatch(rfc9112.HTTP_message, "CONNECT a HTTP/1.1\r\n\r\n"))
        self.assertTrue(fullmatch(old_message, "CONNECT a HTTP/1.1\r\n\r\n"))

    def test_comment_nesting(self) -> None:
        "comment is unrolled to two levels inside the outer one."

        def depth(value: str) -> int:
            "The nesting depth of `value` if it is one comment, or -1 if it isn't."
            level = deepest = pos = 0
            while pos < len(value):
                char = value[pos]
                if level == 0 and pos > 0:
                    return -1  # something follows the comment
                if char == "\\":
                    if level == 0 or pos + 1 >= len(value):
                        return -1
                    pos += 2
                    continue
                if char == "(":
                    level += 1
                    deepest = max(deepest, level)
                elif char == ")":
                    if level == 0:
                        return -1
                    level -= 1
                elif level == 0:
                    return -1
                pos += 1
            return deepest if level == 0 and deepest else -1

        old = rf"(?: \( (?: {rfc9110.ctext} | {rfc9110.quoted_pair} )* \) )"
        for value in strings(["(", ")", "a", "\\", " "], 7):
            with self.subTest(value=value):
                level = depth(value)
                self.assertEqual(fullmatch(rfc9110.comment, value), 1 <= level <= 3)
                self.assertEqual(fullmatch(old, value), level == 1)
        for value in ["(a (b) c)", "(a (b (c)) d)", r"(a (b \) (c)) d)", "()", "(())", "((()))"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9110.comment, value))
        for value in ["((((x))))", "(a (b (c (d))))", "(a (b)", "a (b)"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9110.comment, value))
        self.assertTrue(matches(rfc9110.Server, "a/1 (x (y (z))) b"))
        self.assertTrue(matches(rfc9110.User_Agent, "a/1 (x (y)) (z)"))
        self.assertFalse(matches(rfc9110.User_Agent, "a/1 (x (y (z (w))))"))
        self.assertNotIn("BAD_SYNTAX", field_notes(True, b"Server", b"a/1 (x (y)) b/2"))
        self.assertNotIn("BAD_SYNTAX", field_notes(False, b"User-Agent", b"a/1 (x (y (z)))"))

    def test_http_version(self) -> None:
        for value in ["HTTP/1.1", "HTTP/2.0", "HTTP/0.9"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.HTTP_version, value))
        for value in ["HTTP/1x1", "HTTP/1 1", "HTTP/1,1", "HTTP/11", "http/1.1"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.HTTP_version, value))

    def test_chunked_body_is_transcribed(self) -> None:
        "Never match a body against chunked_body: that backtracks exponentially."
        re.compile(rfc9112.chunked_body, re.VERBOSE)
        self.assertIn(rfc9112.chunk, rfc9112.chunked_body)
        self.assertIn(rfc9112.last_chunk, rfc9112.chunked_body)
        self.assertIn(rfc9112.trailer_section, rfc9112.chunked_body)
        self.assertNotIn("(?: chunk )", rfc9112.chunked_body)
        self.assertFalse(hasattr(rfc9112, "trailer_part"))
        self.assertFalse(hasattr(rfc9112, "header_field"))

    def test_chunk_rules(self) -> None:
        for value in ["5\r\nhello\r\n", "A;x=y\r\nabcdefghij\r\n", "1 ; a = b\r\n\r\n\r\n"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.chunk, value))
        for value in ["\r\n", "g\r\na\r\n", "1\r\n\r\n"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.chunk, value))
        for value in ["0\r\n", "000\r\n", "0;a=b\r\n"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.last_chunk, value))
        for value in ["\r\n", "1\r\n", "0\n"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.last_chunk, value))

    def test_trailer_section(self) -> None:
        for value in ["", "A: b\r\n", "A: b\r\nC:d \r\n", "A:\r\n"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.trailer_section, value))
        for value in ["A: b", "A b\r\n", "\r\n", "A: b\r\n\r\n"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.trailer_section, value))

    def test_chunk_ext(self) -> None:
        for value in ["", ";a", ";a=b", ' ; a = b ;c="d e"', ";a;b=c;d"]:
            with self.subTest(value=value):
                self.assertTrue(fullmatch(rfc9112.chunk_ext, value))
        for value in [";", "a", ";a=", ";=b", ";a b"]:
            with self.subTest(value=value):
                self.assertFalse(fullmatch(rfc9112.chunk_ext, value))


class SyntaxChallengeTest(unittest.TestCase):
    """
    The challenge and credentials rules rejected an empty element before the first auth-param
    (`Basic , realm=x`), which RFC 9110 Section 5.6.1 has recipients accept, and which
    ChallengeField and CredentialsField do.
    """

    def old(self) -> str:
        "The rule as it was."
        param, token68 = rfc9110.auth_param, rfc9110.token68
        return rf"""(?: {rfc9110.auth_scheme}
            (?: {rfc9110.SP}+
                (?: {token68} |
                    (?:
                        (?: , | {param} )
                        (?: {rfc9110.OWS} , (?: {rfc9110.OWS} {param} )? )*
                    )?
                )
            )?
        )"""

    def reference(self) -> str:
        "The rule written as [ auth-param ] *( OWS ',' [ OWS auth-param ] )."
        param, ows = rfc9110.auth_param, rfc9110.OWS
        return rf"""(?: {rfc9110.auth_scheme}
            (?: {rfc9110.SP}+
                (?: {rfc9110.token68} |
                    (?: {param}? (?: {ows} , (?: {ows} {param} )? )* )
                )
            )?
        )"""

    def test_differential(self) -> None:
        old, reference = self.old(), self.reference()
        self.assertEqual(
            len({re.sub(r"\s+", "", r) for r in (rfc9110.challenge, rfc9110.credentials)}), 1
        )
        newly_accepted = 0
        for tail in strings([" ", "a", "=", ",", '"'], 7):
            value = "A" + tail
            with self.subTest(value=value):
                was, now = fullmatch(old, value), fullmatch(rfc9110.challenge, value)
                self.assertEqual(now, fullmatch(rfc9110.credentials, value))
                self.assertEqual(now, fullmatch(reference, value))
                if was:
                    self.assertTrue(now)
                elif now:
                    newly_accepted += 1
                    self.assertIn(",", value)
        self.assertGreater(newly_accepted, 20)

    def test_accept_reject(self) -> None:
        for rule in [rfc9110.challenge, rfc9110.credentials]:
            for value in [
                "Basic , realm=x",
                "Basic ,realm=x",
                "Basic ,, realm=x",
                "Basic , , realm=x, charset=y",
                'Basic ,  realm="x" ,, charset=y,',
                "Basic realm=x",
                "Basic realm=x,",
                "Basic ,",
                "Basic",
                "Basic abc=",
                "Bearer abc.def",
            ]:
                with self.subTest(rule=rule[:30], value=value):
                    self.assertTrue(fullmatch(rule, value))
            for value in [
                "Basic realm=x charset=y",
                "Basic , realm",
                "Basic,realm=x",
                "",
                " , a=b",
            ]:
                with self.subTest(rule=rule[:30], value=value):
                    self.assertFalse(fullmatch(rule, value))
        self.assertTrue(matches(rfc9110.WWW_Authenticate, "Basic , realm=x, Digest a=b"))
        self.assertTrue(matches(rfc9110.Proxy_Authenticate, "Basic , realm=x, Digest , a=b"))
        self.assertTrue(matches(rfc9110.Authorization, "Basic , realm=x"))

    def test_fields_accept_it(self) -> None:
        "Guard: the fields parse these themselves, and already accepted them."
        for response, name in [(True, b"WWW-Authenticate"), (False, b"Authorization")]:
            self.assertNotIn("BAD_SYNTAX", field_notes(response, name, b"Basic , realm=x"))
            self.assertNotIn("BAD_SYNTAX_DETAILED", field_notes(response, name, b"Basic , realm=x"))

    def test_timing(self) -> None:
        "Guard: the rule has no new ambiguity."
        values = [
            "A " + ", " * 2000 + "\x80",
            "A ," + " " * 2000 + "\x80",
            "A " + "a=b, " * 24 + "\x80",
            "A " + ", a=b " * 24 + "\x80",
            "A" + " " * 2000 + "\x80",
            "A , " + "a=b ,  " * 2000 + "\x80",
        ]
        for rule in [rfc9110.challenge, rfc9110.credentials]:
            compiled = re.compile(rf"^\s*(?:{rule})\s*$", re.VERBOSE | re.IGNORECASE)
            for value in values:
                with self.subTest(value=value[:20]):
                    start = time.monotonic()
                    compiled.match(value)
                    self.assertLess(time.monotonic() - start, TIME_LIMIT)


class FieldSyntaxCheckTest(unittest.TestCase):
    """HttpField._check_syntax is shared by list, singleton and broken fields."""

    class SingletonF(SingletonField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = "a+"

    class BrokenF(BrokenField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = "a+"

    class ListF(HttpListField[ResponseLinterProtocol]):
        canonical_name = "X-Test"
        description = "test"
        reference = "https://example.com/"
        syntax = rfc9110.list_rule("a+")

    def lint(self, field_class: Type[HttpField[Any]], *values: str) -> List[Note]:
        message = FakeResponseLinter()
        field = field_class("X-Test", message)
        for offset, value in enumerate(values):
            field.handle_input(value, partial(message.notes.add, "x"), offset)
        field.finish(partial(message.notes.add, "x", field_name="X-Test"))
        return list(message.notes)

    def classes(self, notes: List[Note]) -> List[type]:
        return [n.__class__ for n in notes]

    def test_detailed_note_for_every_kind(self) -> None:
        "A value that matches in part gets the position and context, not just BAD_SYNTAX."
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                notes = self.lint(field_class, "aab")
                self.assertEqual(self.classes(notes), [BAD_SYNTAX_DETAILED])
                self.assertIn("position 3", notes[0].vars["problem"])

    def test_generic_note_when_nothing_matches(self) -> None:
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                self.assertEqual(self.classes(self.lint(field_class, "b")), [BAD_SYNTAX])

    def test_conforming_value(self) -> None:
        for field_class in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(field_class.__bases__[0].__name__):
                self.assertEqual(self.classes(self.lint(field_class, " aaa ")), [])

    def test_note_vars(self) -> None:
        "A character that can't be quoted is named by code point."
        notes = self.lint(self.SingletonF, "a`")
        self.assertIn("U+0060", notes[0].vars["problem"])
        self.assertNotIn("`", notes[0].vars["problem"])

    def test_category(self) -> None:
        "Both notes take the field's category, for every kind of field."
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            categorised = type("Categorised", (base,), {"category": categories.CACHING})
            for value in ("aab", "b"):
                with self.subTest(base.__bases__[0].__name__, value=value):
                    notes = self.lint(categorised, value)
                    self.assertEqual(notes[0].category, categories.CACHING)

    def test_levels(self) -> None:
        "A partial match is BAD (detailed note), no match is WARN (generic note)."
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                self.assertEqual(self.lint(base, "aab")[0].level, levels.BAD)
                self.assertEqual(self.lint(base, "b")[0].level, levels.WARN)

    def test_hook_when_parse_raises(self) -> None:
        "The check still runs when parse() raises ValueError, unless it suppressed it first."

        def raises(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            raise ValueError

        def suppresses_then_raises(
            self: HttpField[Any], field_value: str, add_note: AddNoteMethodType
        ) -> str:
            self.suppress_syntax_note()  # type: ignore[attr-defined]
            raise ValueError

        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                plain = type("Raises", (base,), {"parse": raises})
                quiet = type("Quiet", (base,), {"parse": suppresses_then_raises})
                self.assertEqual(self.classes(self.lint(plain, "b")), [BAD_SYNTAX])
                self.assertEqual(self.lint(quiet, "b"), [])

    def test_report_syntax_false(self) -> None:
        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                quiet = type("Quiet", (base,), {"report_syntax": False})
                self.assertEqual(self.lint(quiet, "aab"), [])
                self.assertEqual(self.lint(quiet, "b"), [])

    def test_suppress_hook(self) -> None:
        "parse() can suppress the note for its own value, and only for that value."

        def parse(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            if field_value.startswith("b"):
                self.suppress_syntax_note()  # type: ignore[attr-defined]
            return field_value

        for base in (self.SingletonF, self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                hooked = type("Hooked", (base,), {"parse": parse})
                self.assertEqual(self.lint(hooked, "b"), [])

    def test_suppress_hook_does_not_leak(self) -> None:
        def parse(self: HttpField[Any], field_value: str, add_note: AddNoteMethodType) -> str:
            if field_value.startswith("b"):
                self.suppress_syntax_note()  # type: ignore[attr-defined]
            return field_value

        for base in (self.BrokenF, self.ListF):
            with self.subTest(base.__bases__[0].__name__):
                hooked = type("Hooked", (base,), {"parse": parse})
                values = ("b", "c") if base is self.BrokenF else ("b, c",)
                self.assertEqual(self.classes(self.lint(hooked, *values)), [BAD_SYNTAX])

    def test_patterns_compiled_once_per_class(self) -> None:
        first = self.SingletonF._syntax_patterns()  # pylint: disable=protected-access
        self.assertIs(first, self.SingletonF._syntax_patterns())  # pylint: disable=protected-access
        child = type("Child", (self.SingletonF,), {"syntax": "b+"})
        self.assertIsNot(first, child._syntax_patterns())  # pylint: disable=protected-access
        self.assertIs(first, self.SingletonF._syntax_patterns())  # pylint: disable=protected-access

    def test_no_syntax(self) -> None:
        none = type("NoSyntax", (self.SingletonF,), {"syntax": False})
        self.assertIsNone(none._syntax_patterns())  # pylint: disable=protected-access
        self.assertEqual(self.lint(none, "anything"), [])


class FieldSyntaxNoteTest(unittest.TestCase):
    """Real fields: one note per defect, and the detailed note for singletons."""

    def notes(self, name: bytes, value: bytes, response: bool = True) -> List[type]:
        linter = HttpResponseLinter() if response else HttpRequestLinter()
        if response:
            linter.process_response_topline(b"HTTP/1.1", b"302", b"Found")
        else:
            linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(name, value)])
        linter.finish_content(True)
        return [n.__class__ for n in linter.notes]

    def test_singleton_detailed(self) -> None:
        self.assertIn(BAD_SYNTAX_DETAILED, self.notes(b"Location", b"http://example.com/a b"))
        self.assertIn(
            BAD_SYNTAX_DETAILED, self.notes(b"Referer", b"http://example.com/a b", response=False)
        )

    def test_hook_users_give_one_note(self) -> None:
        "Location, Referer and Link report an unresolvable URI once, without BAD_SYNTAX."
        for name, value, response, specific in [
            (b"Location", b"http://[", True, LOCATION_BAD_URI),
            (b"Referer", b"https://[::1", False, REFERER_BAD_URI),
            (b"Link", b"<http://[::1>; rel=preload", True, LINK_BAD_TARGET_URI),
        ]:
            with self.subTest(name=name):
                found = self.notes(name, value, response)
                self.assertEqual(found.count(specific), 1, found)
                self.assertFalse(any(issubclass(n, BAD_SYNTAX) for n in found), found)

    def test_order(self) -> None:
        "The note parse() adds comes before the syntax note for the same value."
        found = [
            n
            for n in self.notes(b"Location", b"http://example.com/a b")
            if n in (LOCATION_NOT_ABSOLUTE, BAD_SYNTAX_DETAILED)
        ]
        self.assertEqual(found, [LOCATION_NOT_ABSOLUTE, BAD_SYNTAX_DETAILED])

    def test_hook_suppresses_whole_value(self) -> None:
        "Pins the per-value scope: the stray '>' in this Link isn't reported separately."
        found = self.notes(b"Link", b"<http://[::1>>; rel=dns-prefetch")
        self.assertIn(LINK_BAD_TARGET_URI, found)
        self.assertFalse(any(issubclass(n, BAD_SYNTAX) for n in found), found)

    def problems(self, name: bytes, value: bytes, response: bool = True) -> List[str]:
        linter = HttpResponseLinter() if response else HttpRequestLinter()
        if response:
            linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        else:
            linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(name, value)])
        linter.finish_content(True)
        return [
            str(n.vars["problem"])
            for n in linter.notes
            if issubclass(n.__class__, BAD_SYNTAX_DETAILED)
        ]

    def test_unquotable_character_is_named(self) -> None:
        for name, value, response, expected in [
            (b"Accept-Language", b"a`b", False, "U+0060"),
            (b"Cache-Control", b"a\x00b", True, "U+0000"),
            (b"Allow", b"a\x00b", True, "U+0000"),
            (b"Connection", b"a\x00b", True, "U+0000"),
            (b"WWW-Authenticate", b"Basic `", True, "U+0060"),
        ]:
            with self.subTest(name=name, value=value):
                problems = self.problems(name, value, response)
                self.assertTrue(problems)
                for problem in problems:
                    self.assertIn(expected, problem)
                    self.assertNotIn("''", problem)

    def test_link_hook_is_per_element(self) -> None:
        found = self.notes(b"Link", b"<http://[::1>; rel=preload, </a b>")
        self.assertEqual(sum(1 for n in found if n is BAD_SYNTAX), 1, found)


class InvalidCharProblemTest(unittest.TestCase):
    def test_quoted(self) -> None:
        self.assertEqual(
            invalid_char_problem("ab c", 2), "The invalid character ' ' was found at position 3."
        )
        self.assertEqual(
            invalid_char_problem("a\x80", 1),
            "The invalid character '\x80' was found at position 2.",
        )

    def test_named(self) -> None:
        for char, name in [
            ("`", "U+0060"),
            ("\x00", "U+0000"),
            ("\n", "U+000A"),
            ("\u2028", "U+2028"),
        ]:
            with self.subTest(name):
                problem = invalid_char_problem(f"a{char}b", 1)
                self.assertEqual(problem, f"The invalid character {name} was found at position 2.")

    def test_end_of_value(self) -> None:
        self.assertEqual(
            invalid_char_problem("ab", 2), "The value ended unexpectedly at position 3."
        )


def run_regex_check() -> None:
    print("Checking Syntax...")
    count, modules, errors = check_regex()
    print(f"Checked {count} syntax regex in {modules} modules; {errors} errors.")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_regex_check()
    unittest.main()
