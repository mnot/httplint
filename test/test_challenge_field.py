"""
parse_challenges must follow the RFC 9110 Section 11.6.1 challenge grammar, in linear time.
"""

import itertools
import random
import re
import time
import unittest

from httplint.field.challenge_field import parse_challenges
from httplint.field.tests import FakeRequestLinter, FakeResponseLinter
from test.slow import Mismatches, size

# Generous: linear inputs take well under a second.
TIME_LIMIT = 5.0
SIZE = 100_000


def parse(text):
    "The challenges and the first error (or None)."
    challenges, _, errors = parse_challenges(text)
    return challenges, (errors[0] if errors else None)


def parse_all(text):
    "The challenges and every error."
    challenges, _, errors = parse_challenges(text)
    return challenges, errors


class ChallengeExamplesTest(unittest.TestCase):
    def test_rfc9110_example(self):
        # RFC 9110 Section 11.6.1
        self.assertEqual(
            parse(
                'Newauth realm="apps", type=1, title="Login to \\"apps\\"", '
                'Basic realm="simple"'
            ),
            (
                [
                    ("newauth", {"realm": "apps", "type": "1", "title": 'Login to "apps"'}),
                    ("basic", {"realm": "simple"}),
                ],
                None,
            ),
        )

    def test_rfc7617_examples(self):
        self.assertEqual(
            parse('Basic realm="foo", charset="UTF-8"'),
            ([("basic", {"realm": "foo", "charset": "UTF-8"})], None),
        )
        self.assertEqual(
            parse("Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="),
            ([("basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")], None),
        )
        self.assertEqual(parse("Basic dGVzdDoxMjPCow=="), ([("basic", "dGVzdDoxMjPCow==")], None))

    def test_rfc7616_examples(self):
        challenge = (
            'Digest realm="http-auth@example.org", qop="auth, auth-int", algorithm=SHA-256, '
            'nonce="7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v", '
            'opaque="FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS"'
        )
        self.assertEqual(
            parse(challenge + ", " + challenge.replace("SHA-256", "MD5")),
            (
                [
                    (
                        "digest",
                        {
                            "realm": "http-auth@example.org",
                            "qop": "auth, auth-int",
                            "algorithm": algorithm,
                            "nonce": "7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v",
                            "opaque": "FQhe/qaU925kfnzjCev0ciny7QMkPqMAFRtzCUYo5tdS",
                        },
                    )
                    for algorithm in ("SHA-256", "MD5")
                ],
                None,
            ),
        )

    def test_scheme_only(self):
        self.assertEqual(parse("Bearer"), ([("bearer", {})], None))
        self.assertEqual(
            parse("Bearer, Basic realm=x, Negotiate"),
            ([("bearer", {}), ("basic", {"realm": "x"}), ("negotiate", {})], None),
        )

    def test_token68_then_challenge(self):
        self.assertEqual(
            parse("Negotiate YII=, Basic realm=x"),
            ([("negotiate", "YII="), ("basic", {"realm": "x"})], None),
        )

    def test_comma_in_quoted_string(self):
        self.assertEqual(
            parse('Basic realm="a, Digest b=c"'),
            ([("basic", {"realm": "a, Digest b=c"})], None),
        )

    def test_scheme_and_param_names_are_lowercased_first_wins(self):
        self.assertEqual(
            parse("BASIC Realm=A, REALM=b"), ([("basic", {"realm": "A"})], None)
        )
        self.assertEqual(parse("NeGoTiAte YII="), ([("negotiate", "YII=")], None))

    def test_empty_elements(self):
        self.assertEqual(parse(""), ([], None))
        self.assertEqual(parse(" , ,"), ([], None))
        self.assertEqual(
            parse(",Basic realm=a,, ,Digest b=c,"),
            ([("basic", {"realm": "a"}), ("digest", {"b": "c"})], None),
        )

    def test_empty_elements_in_params(self):
        self.assertEqual(
            parse("Basic realm=x,,,charset=y"),
            ([("basic", {"realm": "x", "charset": "y"})], None),
        )
        self.assertEqual(
            parse("Basic a=b,,c=d, ,\te=f,"),
            ([("basic", {"a": "b", "c": "d", "e": "f"})], None),
        )
        self.assertEqual(parse("Basic , ,a=b"), ([("basic", {"a": "b"})], None))

    def test_bws(self):
        self.assertEqual(parse('Basic realm = "a"'), ([("basic", {"realm": "a"})], None))

    def test_errors(self):
        # (text, challenges kept, first error index)
        for text, kept, error in [
            ('Basic realm="x" charset=y', [("basic", {"realm": "x"})], 16),
            ('Basic realm="x', [], 12),
            ("Basic abc extra", [], 10),
            ("Basic abc  def", [], 11),
            ("Negotiate abc def", [], 14),
            ('a b="', [], 4),
            ("Basic realm=My Realm", [("basic", {"realm": "My"})], 15),
            ("Basic realm=", [("basic", "realm=")], None),
            ("Basic =x", [], 6),
            ("Basic\tx", [], 6),
            ("Basic\ta=b", [], 6),
            ("Basic  \ta=b", [], 8),
            ("Basic a, b c d", [("basic", "a")], 13),
            ("@@@", [], 0),
            ('Basic realm="x", @', [("basic", {"realm": "x"})], 17),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse(text), (kept, error))

    def test_starts(self):
        text = 'Basic realm="x",  Digest a=b, Bearer'
        _, starts, errors = parse_challenges(text)
        self.assertEqual(errors, [])
        self.assertEqual(
            [text[s:].split()[0].rstrip(",") for s in starts], ["Basic", "Digest", "Bearer"]
        )


class ResyncTest(unittest.TestCase):
    "After a syntax error in a list, parsing resumes at the next comma outside a quote."

    def test_unquoted_realm_with_space(self):
        text = "Basic realm=My Realm, Digest a=b"
        self.assertEqual(
            parse_all(text),
            ([("basic", {"realm": "My"}), ("digest", {"a": "b"})], [text.index("Realm")]),
        )

    def test_defect_in_first_challenge_with_good_ones_after(self):
        text = "@@@, Basic realm=a, Digest b=c, Bearer abc=="
        self.assertEqual(
            parse_all(text),
            (
                [("basic", {"realm": "a"}), ("digest", {"b": "c"}), ("bearer", "abc==")],
                [0],
            ),
        )

    def test_two_defects_in_one_line(self):
        text = "Basic realm=My Realm, Digest a=b c, Bearer abc"
        self.assertEqual(
            parse_all(text),
            (
                [("basic", {"realm": "My"}), ("digest", {"a": "b"}), ("bearer", "abc")],
                [text.index("Realm"), text.index(" c,") + 1],
            ),
        )

    def test_commas_in_quotes_dont_resync(self):
        text = 'Basic realm="a, b" x, Digest c=d'
        self.assertEqual(
            parse_all(text),
            ([("basic", {"realm": "a, b"}), ("digest", {"c": "d"})], [text.index(" x") + 1]),
        )
        # a quoted-string in the broken part of the line is skipped as a whole
        text = 'Basic a=b "x, y", Digest c=d'
        self.assertEqual(
            parse_all(text),
            ([("basic", {"a": "b"}), ("digest", {"c": "d"})], [text.index('"')]),
        )

    def test_unterminated_quote_swallows_the_rest(self):
        # There's no closing quote, so no comma after it is outside a quoted-string.
        self.assertEqual(parse_all('Basic realm="x, Digest a=b'), ([], [12]))
        text = 'Basic realm="a", Bad "y, Digest a=b'
        self.assertEqual(
            parse_all(text), ([("basic", {"realm": "a"})], [text.index('"y')])
        )

    def test_leftover_params_are_not_reported_again(self):
        text = "Basic a=b c=d, e=f, g=h x, Digest i=j"
        self.assertEqual(
            parse_all(text),
            ([("basic", {"a": "b"}), ("digest", {"i": "j"})], [text.index("c=d")]),
        )

    def test_no_more_commas(self):
        self.assertEqual(parse_all("Basic a=b c=d"), ([("basic", {"a": "b"})], [10]))

    def test_credentials_stop_at_the_first_error(self):
        challenges, _, errors = parse_challenges("Basic a=b c, Digest d=e", single=True)
        self.assertEqual((challenges, errors), ([("basic", {"a": "b"})], [10]))


class ProblemTextTest(unittest.TestCase):
    "The note names the character the error is at, and its position."

    def problems(self, linter, name, value):
        linter.headers.process([(name, value)])
        linter.post_checks()
        notes = [n for n in linter.notes if n.__class__.__name__ == "BAD_SYNTAX_DETAILED"]
        return [n.vars["problem"] for n in notes]

    def problem(self, linter, name, value):
        problems = self.problems(linter, name, value)
        self.assertEqual(len(problems), 1)
        return problems[0]

    def test_after_token68(self):
        self.assertEqual(
            self.problem(FakeRequestLinter(), b"Authorization", b"Basic abc extra"),
            "The invalid character 'e' was found at position 11.",
        )
        self.assertEqual(
            self.problem(FakeResponseLinter(), b"WWW-Authenticate", b"Negotiate abc def"),
            "The invalid character 'd' was found at position 15.",
        )

    def test_unterminated_quote(self):
        self.assertEqual(
            self.problem(FakeResponseLinter(), b"WWW-Authenticate", b'Basic realm="x'),
            "The invalid character '\"' was found at position 13.",
        )

    def test_empty(self):
        self.assertEqual(
            self.problem(FakeRequestLinter(), b"Authorization", b""),
            "The value ended unexpectedly at position 1.",
        )

    def test_one_note_per_defect(self):
        self.assertEqual(
            self.problems(
                FakeResponseLinter(),
                b"WWW-Authenticate",
                b"Basic realm=My Realm, Digest a=b c, Bearer abc",
            ),
            [
                "The invalid character 'R' was found at position 16.",
                "The invalid character 'c' was found at position 34.",
            ],
        )
        self.assertEqual(
            self.problems(
                FakeResponseLinter(), b"WWW-Authenticate", b"Basic realm=a, Digest b=c"
            ),
            [],
        )

    def test_credentials_get_one_note(self):
        self.assertEqual(
            len(
                self.problems(
                    FakeRequestLinter(), b"Authorization", b"Basic a=b c, Digest d=e f"
                )
            ),
            1,
        )


class CredentialsTest(unittest.TestCase):
    "single=True: one credentials, which isn't a list."

    def test_valid(self):
        for text, expected in [
            ("Basic", {}),
            ("Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==", "QWxhZGRpbjpvcGVuIHNlc2FtZQ=="),
            ('Digest username="Mufasa", realm=x', {"username": "Mufasa", "realm": "x"}),
            ("Digest a=b,", {"a": "b"}),
            ("Digest a=b,,c=d", {"a": "b", "c": "d"}),
        ]:
            with self.subTest(text=text):
                challenges, _, errors = parse_challenges(text, single=True)
                self.assertEqual(errors, [])
                self.assertEqual(challenges, [(text.split()[0].rstrip(",").lower(), expected)])

    def test_errors(self):
        # (text, error index): none of these is a valid credentials
        for text, error in [
            ("", 0),
            (",", 0),
            (", Basic abc", 0),
            ("Basic abc,", 9),
            ("Basic,", 5),
            ("Basic abc, Digest a=b", 9),
            ("Basic a=b, Digest c=d", 11),
            ("Basic abc extra", 10),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse_challenges(text, single=True)[2], [error])


# The RFC 9110 grammar, written out with its own character classes (not httplint.syntax),
# so that a mistake in those rules can't hide in both places.
TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
TOKEN68 = r"[0-9A-Za-z._~+/-]+=*"
QUOTED = r'"(?:[\t \x21\x23-\x5b\x5d-\x7e]|\\[\t \x21-\x7e])*"'
AUTH_PARAM = rf"(?:{TOKEN}[ \t]*=[ \t]*(?:{TOKEN}|{QUOTED}))"
CHALLENGE = (
    rf"(?:{TOKEN}(?:[ ]+(?:{TOKEN68}|(?:{AUTH_PARAM})?(?:[ \t]*,[ \t]*(?:{AUTH_PARAM})?)*))?)"
)
OWS = r"[ \t]*"
GRAMMAR = re.compile(rf"{OWS}(?:{CHALLENGE})?(?:{OWS},{OWS}(?:{CHALLENGE})?)*{OWS}")
PARAM_FIND = re.compile(rf"(?P<name>{TOKEN})[ \t]*=[ \t]*(?P<value>{TOKEN}|{QUOTED})")


class ChallengeGrammarTest(unittest.TestCase):
    """
    Over every short string from small alphabets, the parser must accept exactly what the
    RFC 9110 challenge grammar (with the list syntax's empty elements) does, and its values
    and error positions must be consistent with the text. Resyncing after an error must not
    change which strings are accepted.
    """

    def check(self, text):
        challenges, starts, errors = parse_challenges(text)
        self.assertEqual(not errors, bool(GRAMMAR.fullmatch(text)), repr(text))
        self.assertEqual(len(challenges), len(starts), repr(text))
        self.assertEqual(starts, sorted(set(starts)), repr(text))
        self.assertEqual(errors, sorted(set(errors)), repr(text))
        if errors:
            error = errors[0]
            self.assertLessEqual(errors[-1], len(text), repr(text))
            # Everything before the first error is acceptable: either as it stands, or when
            # what follows it (a value after "=", say) is supplied.
            if error < len(text):
                before = text[:error]
                self.assertTrue(
                    GRAMMAR.fullmatch(before) or GRAMMAR.fullmatch(before + "a"), repr(text)
                )
        for (scheme, value), start in zip(challenges, starts):
            self.assertEqual(text[start : start + len(scheme)].lower(), scheme, repr(text))
            if isinstance(value, str):
                self.assertTrue(re.fullmatch(TOKEN68, value), repr(text))
                self.assertEqual(text[start + len(scheme) :].lstrip(" ")[: len(value)], value)
                continue
            rest = text[start + len(scheme) :]
            found = {}
            for match in PARAM_FIND.finditer(rest):
                raw = match.group("value")
                if raw.startswith('"'):
                    raw = re.sub(r"\\(.)", r"\1", raw[1:-1])
                found.setdefault(match.group("name").lower(), []).append(raw)
            for name, param_value in value.items():
                self.assertIn(param_value, found.get(name, []), repr(text))

    def test_matches_grammar(self):
        bad = Mismatches()
        for alphabet, max_length in (('a= ,"\t', 6), ('a= ,"\t\\/-', size(5, 6))):
            for length in range(0, max_length + 1):
                for chars in itertools.product(alphabet, repeat=length):
                    text = "".join(chars)
                    with bad.case(text):
                        self.check(text)
        bad.assert_none(self)
        self.assertGreater(bad.cases, size(50_000, 500_000))

    def test_matches_grammar_longer_samples(self):
        pieces = ["Basic", " ", "realm", "=", '"x, y"', ",", " , ", "abc==", "a\\b", '"', "\t"]
        rng = random.Random(1)
        for _ in range(20_000):
            self.check("".join(rng.choice(pieces) for _ in range(rng.randint(1, 10))))


class ChallengeTimingTest(unittest.TestCase):
    def assert_fast(self, text):
        start = time.monotonic()
        parse_challenges(text)
        self.assertLess(time.monotonic() - start, TIME_LIMIT)

    def test_long_runs(self):
        self.assert_fast("a" * SIZE)
        self.assert_fast("a " + "a" * SIZE)
        self.assert_fast("a " + "a" * SIZE + "=" * SIZE)
        self.assert_fast("a " + "a" * SIZE + "= b")
        self.assert_fast("a" * SIZE + "=")
        self.assert_fast("a " * SIZE)
        self.assert_fast("a" + " " * SIZE + "b")
        self.assert_fast("a" + "\t" * SIZE + "b")

    def test_many_elements(self):
        self.assert_fast("a," * SIZE)
        self.assert_fast("," * SIZE)
        self.assert_fast(", " * SIZE + "a")
        self.assert_fast("a b," * (SIZE // 4))
        self.assert_fast("a b=c, " * (SIZE // 7))
        self.assert_fast("a b=," * (SIZE // 5))
        self.assert_fast("a " + "b=c," * (SIZE // 4))
        self.assert_fast("a " + "b=c ," * (SIZE // 5))
        self.assert_fast("a " + "b=c d" * (SIZE // 5))

    def test_quoted_strings(self):
        self.assert_fast('a b="' + "a" * SIZE)
        self.assert_fast('a b="' + "\\" * SIZE)
        self.assert_fast('a b="' + "\\a" * SIZE + '"')
        self.assert_fast('a b="' + "," * SIZE + '"')
        self.assert_fast('a b="x", ' * (SIZE // 9))
        self.assert_fast('a b="' * (SIZE // 5))

    def test_many_errors_and_resyncs(self):
        # Every element is a defect, so each triggers a resync.
        self.assert_fast("@," * SIZE)
        self.assert_fast("@" * SIZE)
        self.assert_fast("a b c," * (SIZE // 6))
        self.assert_fast("a b=c d," * (SIZE // 8))
        self.assert_fast("a b=c d, e=f," * (SIZE // 13))
        self.assert_fast("a b=c d, " + "e=f, " * SIZE + "g")
        self.assert_fast("a b=c d" + " e=f" * SIZE)
        self.assert_fast('a b=c d "x, y", ' * (SIZE // 15))
        self.assert_fast('a b=c d "' + "x, " * SIZE)
        self.assert_fast('a b=c d "' + "\\" * SIZE)
        self.assert_fast("a b=c d, e=" + " " * SIZE + "x")
        self.assert_fast("a b=c d, e" + " " * SIZE + "=")
        self.assert_fast("a b=c d," + "e=" * SIZE)
        self.assert_fast("a @ " + 'b="x" y ' * (SIZE // 8))


if __name__ == "__main__":
    unittest.main()
