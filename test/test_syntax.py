import importlib
import itertools
import re
import sys
import time
import unittest
from typing import Callable, List, Tuple

from httplint import HttpRequestLinter, HttpResponseLinter, syntax
from httplint.syntax import rfc5646, rfc9110, rfc9112, rfc9651


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


def case_variants(value: str) -> List[str]:
    "The value, in lower and upper case, and with each letter's case flipped in turn."
    variants = [value, value.lower(), value.upper()]
    for i, char in enumerate(value):
        if char.isalpha():
            variants.append(value[:i] + char.swapcase() + value[i + 1 :])
    return variants


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


def run_regex_check() -> None:
    print("Checking Syntax...")
    count, modules, errors = check_regex()
    print(f"Checked {count} syntax regex in {modules} modules; {errors} errors.")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_regex_check()
    unittest.main()
