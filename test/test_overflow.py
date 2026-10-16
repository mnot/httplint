"""
Attacker-controlled field values must not make linting or note rendering raise.
"""

import pytest

from httplint import HttpResponseLinter
from httplint.field.json_field import BAD_JSON
from httplint.util import relative_time


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


def freshness_notes(*headers):
    linter = HttpResponseLinter(start_time=1.7e9)
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(list(headers))
    linter.finish_content(True)
    return linter, [type(n).__name__ for n in linter.notes]


def test_far_future_expires_unchanged():
    date = (b"Date", b"Thu, 01 Jan 2026 00:00:00 GMT")
    for expires, years in [
        (b"Sun, 01 Jan 2200 00:00:00 GMT", "174 years"),
        (b"Fri, 31 Dec 9999 23:59:59 GMT", "7979 years"),
    ]:
        linter, _ = freshness_notes(date, (b"Expires", expires))
        assert any(years in n.summary for n in linter.notes), years


def test_far_future_cookie_expires_renders():
    linter, _ = freshness_notes(
        (b"Date", b"Thu, 01 Jan 2026 00:00:00 GMT"),
        (b"Set-Cookie", b"a=b; Expires=Fri, 31 Dec 9999 23:59:59 GMT"),
    )
    render_all(linter)
    assert any("years" in n.detail for n in linter.notes)


def test_clamp_changes_freshness_verdict():
    linter, names = freshness_notes(
        (b"Age", b"3000000000"), (b"Cache-Control", b"max-age=3000001000")
    )
    assert "FRESHNESS_STALE_CACHE" in names or "FRESHNESS_STALE_ALREADY" in names
    assert linter.headers.parsed["age"] == 3000000000
    assert linter.caching.age == 2147483648
    assert linter.caching.freshness_lifetime_private == 2147483648
    assert not linter.caching.is_fresh


def test_huge_negative_max_age():
    render_all(lint(b"Cache-Control", b"max-age=-" + BIG))


def test_relative_time_extremes():
    for utime, now in [(10**400, 1.7e9), (-(10**400), 1.7e9), (float("nan"), 0), (float("inf"), 0)]:
        assert str(relative_time(utime, now))


def test_json_depth_consistent():
    deep = b"[" * 500 + b"]" * 500
    assert BAD_JSON in [type(n) for n in lint(b"Report-To", deep).notes]
    shallow = b"[" * 50 + b"]" * 50
    assert BAD_JSON not in [type(n) for n in lint(b"Report-To", shallow).notes]
