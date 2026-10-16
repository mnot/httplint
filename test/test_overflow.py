"""
Attacker-controlled field values must not make linting or note rendering raise.
"""

import pytest

from httplint import HttpResponseLinter
from httplint.field.json_field import BAD_JSON
from httplint.util import MAX_DELTA_SECONDS, relative_time


def lint(name, value):
    linter = HttpResponseLinter(start_time=1.7e9)
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(name, value)])
    linter.finish_content(True)
    return linter


def render_all(linter):
    for note in linter.notes:
        assert note.summary
        assert note.detail


@pytest.mark.parametrize("name", [b"NEL", b"Report-To"])
@pytest.mark.parametrize(
    "value",
    [b"[" * 100000, b'{"a":' * 50000, b'{"max_age": ' + b"9" * 5000 + b"}"],
)
def test_json_pathological(name, value):
    linter = lint(name, value)
    assert BAD_JSON in [type(n) for n in linter.notes]
    render_all(linter)


BIG = b"9" * 30


@pytest.mark.parametrize(
    "name,value",
    [
        (b"Age", BIG),
        (b"Cache-Control", b"max-age=" + BIG),
        (b"Cache-Control", b"s-maxage=" + BIG + b", max-age=5"),
        (b"Cache-Control", b"max-age=" + BIG + b", s-maxage=5"),
        (b"Set-Cookie", b"a=b; Max-Age=" + BIG),
    ],
)
def test_huge_delta_seconds_render(name, value):
    render_all(lint(name, value))


def test_delta_seconds_not_clamped_in_parsed():
    linter = lint(b"Age", BIG)
    assert linter.headers.parsed["age"] == int(BIG)


def test_relative_time_clamps():
    big = str(relative_time(10**30, 0, 0))
    assert big == str(relative_time(MAX_DELTA_SECONDS, 0, 0))
    str(relative_time(-(10**30), 0))
