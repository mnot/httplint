"""
parse_params uses the first instance of a repeated parameter -- the first instance as
written, even if it's invalid or rejected, as RFC 8288 and the Server Timing
specification say.
"""

import unittest

from httplint.field.utils import (
    PARAM_REPEATS,
    PARAM_STAR_BAD,
    PARAM_STAR_ERROR,
    PARAM_STAR_QUOTED,
    parse_params,
)


def parse(instr, nostar=None):
    notes = []

    def add_note(cls, **kwargs):
        notes.append((cls, kwargs["param"]))

    return parse_params(instr, add_note, nostar), notes


class ParseParamsTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse("a=1; B=2"), ({"a": "1", "b": "2"}, []))
        self.assertEqual(parse(";;a=1;;"), ({"a": "1"}, []))
        self.assertEqual(parse(""), ({}, []))

    def test_first_instance_wins(self):
        self.assertEqual(parse("a=1; b=2; A=3"), ({"a": "1", "b": "2"}, [(PARAM_REPEATS, "a")]))
        self.assertEqual(parse('a="x;y"; a=z'), ({"a": "x;y"}, [(PARAM_REPEATS, "a")]))
        self.assertEqual(parse("a=1; a=2; a=3"), ({"a": "1"}, [(PARAM_REPEATS, "a")] * 2))

    def test_rejected_star_value_still_counts_as_the_first(self):
        # RFC 8288 Section 3.4.1: title* after the first is ignored, whatever the first was.
        self.assertEqual(
            parse("title*=bogus; title*=UTF-8''%41"),
            ({}, [(PARAM_STAR_ERROR, "title*"), (PARAM_REPEATS, "title*")]),
        )
        self.assertEqual(
            parse("title*=bogus; title*=UTF-8''d; title*=UTF-8''e"),
            (
                {},
                [
                    (PARAM_STAR_ERROR, "title*"),
                    (PARAM_REPEATS, "title*"),
                    (PARAM_REPEATS, "title*"),
                ],
            ),
        )
        self.assertEqual(
            parse("title*=UTF-8''a; title*=bogus"),
            ({"title*": "a"}, [(PARAM_REPEATS, "title*")]),
        )

    def test_star_parameter_that_isnt_allowed_still_counts(self):
        self.assertEqual(
            parse("x*=UTF-8''a; x*=UTF-8''b", nostar=True),
            ({}, [(PARAM_STAR_BAD, "x"), (PARAM_REPEATS, "x*")]),
        )
        self.assertEqual(
            parse("x*=UTF-8''a; x*=UTF-8''b", nostar=["x"]),
            ({}, [(PARAM_STAR_BAD, "x"), (PARAM_REPEATS, "x*")]),
        )

    def test_star_and_plain_are_separate_parameters(self):
        self.assertEqual(
            parse("title=a; title*=UTF-8''b; title=c"),
            ({"title": "a", "title*": "b"}, [(PARAM_REPEATS, "title")]),
        )

    def test_invalid_first_instance_still_counts_as_the_first(self):
        # Server Timing: "only the first instance is to be considered, even if the
        # server-timing-param is incomplete or invalid".
        for instr in [
            "dur=; dur=5",  # empty value
            "dur=a b; dur=5",  # a space in an unquoted value
            "dur; dur=5",  # no value
            'dur="unterminated; dur=5',
            "dur=1 2; dur=5",
        ]:
            with self.subTest(instr=instr):
                self.assertEqual(parse(instr), ({}, [(PARAM_REPEATS, "dur")]))
        # ... and the other way round: the valid first instance wins, the invalid one is a repeat.
        self.assertEqual(parse("dur=5; dur="), ({"dur": "5"}, [(PARAM_REPEATS, "dur")]))
        self.assertEqual(parse("dur=5; dur"), ({"dur": "5"}, [(PARAM_REPEATS, "dur")]))

    def test_text_that_isnt_a_parameter_is_still_skipped(self):
        # Unchanged: only a name that repeats matters.
        self.assertEqual(parse("a=b c=d"), ({"c": "d"}, []))
        self.assertEqual(parse("a; b=1"), ({"b": "1"}, []))
        self.assertEqual(parse('a="b;c=d"; e=f'), ({"a": "b;c=d", "e": "f"}, []))
        self.assertEqual(parse("=x; a=1"), ({"a": "1"}, []))

    def test_quoted_star_value(self):
        self.assertEqual(
            parse("x*=\"UTF-8''a\"; x*=UTF-8''b"),
            ({"x*": "a"}, [(PARAM_STAR_QUOTED, "x*"), (PARAM_REPEATS, "x*")]),
        )


if __name__ == "__main__":
    unittest.main()
