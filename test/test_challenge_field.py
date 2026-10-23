"""
parse_challenges must follow the RFC 9110 Section 11.6.1 challenge grammar, in linear time.
"""

import itertools
import re
import time
import unittest

from httplint.field.challenge_field import parse_challenges
from httplint.field.utils import RE_FLAGS
from httplint.syntax import rfc9110

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

    def test_bws(self):
        self.assertEqual(parse('Basic realm = "a"'), ([("Basic", {"realm": "a"})], None))

    def test_errors(self):
        # (text, challenges kept, error index)
        for text, kept, error in [
            ('Basic realm="x" charset=y', [("Basic", {"realm": "x"})], 16),
            ('Basic realm="x', [], 6),
            ("Basic realm=", [("Basic", "realm=")], None),
            ("Basic =x", [], 6),
            ("Basic\tx", [], 6),
            ("Basic\ta=b", [], 6),
            ("Basic  \ta=b", [], 8),
            ("Basic a, b c d", [("Basic", "a")], 11),
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


class ChallengeGrammarTest(unittest.TestCase):
    """
    Over every short string from a small alphabet, the parser must accept exactly what the
    RFC 9110 challenge grammar (with the list syntax's empty elements) does.
    """

    def test_matches_grammar(self):
        ows = rfc9110.OWS
        param = rfc9110.auth_param
        challenge = (
            rf"(?: {rfc9110.auth_scheme} (?: [ ]+ (?: {rfc9110.token68} | "
            rf"(?: {param} )? (?: {ows} , {ows} (?: {param} )? )* ) )? )"
        )
        grammar = re.compile(
            rf"{ows} (?: {challenge} )? (?: {ows} , {ows} (?: {challenge} )? )* {ows}",
            RE_FLAGS,
        )
        checked = 0
        for length in range(0, 7):
            for chars in itertools.product("a= ,\"\t", repeat=length):
                text = "".join(chars)
                checked += 1
                _, _, error = parse_challenges(text)
                self.assertEqual(error is None, bool(grammar.fullmatch(text)), repr(text))
        self.assertGreater(checked, 50_000)


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
