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

# Generous: linear inputs take well under a second.
TIME_LIMIT = 5.0
SIZE = 100_000


def parse(text):
    challenges, _, error = parse_challenges(text)
    return challenges, error


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
                    ("Newauth", {"realm": "apps", "type": "1", "title": 'Login to "apps"'}),
                    ("Basic", {"realm": "simple"}),
                ],
                None,
            ),
        )

    def test_rfc7617_examples(self):
        self.assertEqual(
            parse('Basic realm="foo", charset="UTF-8"'),
            ([("Basic", {"realm": "foo", "charset": "UTF-8"})], None),
        )
        self.assertEqual(
            parse("Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="),
            ([("Basic", "QWxhZGRpbjpvcGVuIHNlc2FtZQ==")], None),
        )
        self.assertEqual(
            parse("Basic dGVzdDoxMjPCow=="), ([("Basic", "dGVzdDoxMjPCow==")], None)
        )

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
                        "Digest",
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
        self.assertEqual(parse("Bearer"), ([("Bearer", {})], None))
        self.assertEqual(
            parse("Bearer, Basic realm=x, Negotiate"),
            ([("Bearer", {}), ("Basic", {"realm": "x"}), ("Negotiate", {})], None),
        )

    def test_token68_then_challenge(self):
        self.assertEqual(
            parse("Negotiate YII=, Basic realm=x"),
            ([("Negotiate", "YII="), ("Basic", {"realm": "x"})], None),
        )

    def test_comma_in_quoted_string(self):
        self.assertEqual(
            parse('Basic realm="a, Digest b=c"'),
            ([("Basic", {"realm": "a, Digest b=c"})], None),
        )

    def test_param_names_are_case_insensitive_first_wins(self):
        self.assertEqual(
            parse("Basic Realm=a, REALM=b"), ([("Basic", {"realm": "a"})], None)
        )

    def test_empty_elements(self):
        self.assertEqual(parse(""), ([], None))
        self.assertEqual(parse(" , ,"), ([], None))
        self.assertEqual(
            parse(",Basic realm=a,, ,Digest b=c,"),
            ([("Basic", {"realm": "a"}), ("Digest", {"b": "c"})], None),
        )

    def test_empty_elements_in_params(self):
        self.assertEqual(
            parse("Basic realm=x,,,charset=y"),
            ([("Basic", {"realm": "x", "charset": "y"})], None),
        )
        self.assertEqual(
            parse("Basic a=b,,c=d, ,\te=f,"),
            ([("Basic", {"a": "b", "c": "d", "e": "f"})], None),
        )
        self.assertEqual(
            parse("Basic , ,a=b"), ([("Basic", {"a": "b"})], None)
        )

    def test_bws(self):
        self.assertEqual(parse('Basic realm = "a"'), ([("Basic", {"realm": "a"})], None))

    def test_errors(self):
        # (text, challenges kept, error index)
        for text, kept, error in [
            ('Basic realm="x" charset=y', [("Basic", {"realm": "x"})], 16),
            ('Basic realm="x', [], 12),
            ("Basic abc extra", [], 10),
            ("Basic abc  def", [], 11),
            ("Negotiate abc def", [], 14),
            ('a b="', [], 4),
            ("Basic realm=My Realm", [("Basic", {"realm": "My"})], 15),
            ("Basic realm=", [("Basic", "realm=")], None),
            ("Basic =x", [], 6),
            ("Basic\tx", [], 6),
            ("Basic\ta=b", [], 6),
            ("Basic  \ta=b", [], 8),
            ("Basic a, b c d", [("Basic", "a")], 13),
            ("@@@", [], 0),
            ('Basic realm="x", @', [("Basic", {"realm": "x"})], 17),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse(text), (kept, error))

    def test_starts(self):
        text = 'Basic realm="x",  Digest a=b, Bearer'
        _, starts, error = parse_challenges(text)
        self.assertIsNone(error)
        self.assertEqual([text[s:].split()[0].rstrip(",") for s in starts], [
            "Basic", "Digest", "Bearer"
        ])


class ProblemTextTest(unittest.TestCase):
    "The note names the character the error is at, and its position."

    def problem(self, linter, name, value):
        linter.headers.process([(name, value)])
        linter.post_checks()
        notes = [n for n in linter.notes if n.__class__.__name__ == "BAD_SYNTAX_DETAILED"]
        self.assertEqual(len(notes), 1)
        return notes[0].vars["problem"]

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
                challenges, _, error = parse_challenges(text, single=True)
                self.assertIsNone(error)
                self.assertEqual(challenges, [(text.split()[0].rstrip(","), expected)])

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
                self.assertEqual(parse_challenges(text, single=True)[2], error)


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
    and error positions must be consistent with the text.
    """

    def check(self, text):
        challenges, starts, error = parse_challenges(text)
        self.assertEqual(error is None, bool(GRAMMAR.fullmatch(text)), repr(text))
        self.assertEqual(len(challenges), len(starts), repr(text))
        self.assertEqual(starts, sorted(set(starts)), repr(text))
        if error is not None:
            self.assertLessEqual(error, len(text), repr(text))
            # Everything before the error is acceptable: either as it stands, or when what
            # follows it (a value after "=", say) is supplied.
            if error < len(text):
                before = text[:error]
                self.assertTrue(
                    GRAMMAR.fullmatch(before) or GRAMMAR.fullmatch(before + "a"), repr(text)
                )
        for (scheme, value), start in zip(challenges, starts):
            self.assertEqual(text[start : start + len(scheme)], scheme, repr(text))
            end = len(text)
            if isinstance(value, str):
                self.assertTrue(re.fullmatch(TOKEN68, value), repr(text))
                self.assertEqual(text[start + len(scheme) :].lstrip(" ")[: len(value)], value)
                continue
            rest = text[start + len(scheme) : end]
            found = {}
            for match in PARAM_FIND.finditer(rest):
                raw = match.group("value")
                if raw.startswith('"'):
                    raw = re.sub(r"\\(.)", r"\1", raw[1:-1])
                found.setdefault(match.group("name").lower(), []).append(raw)
            for name, param_value in value.items():
                self.assertIn(param_value, found.get(name, []), repr(text))

    def test_matches_grammar(self):
        checked = 0
        for alphabet, max_length in (('a= ,"\t', 6), ('a= ,"\t\\/-', 6)):
            for length in range(0, max_length + 1):
                for chars in itertools.product(alphabet, repeat=length):
                    checked += 1
                    self.check("".join(chars))
        self.assertGreater(checked, 500_000)

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


if __name__ == "__main__":
    unittest.main()
