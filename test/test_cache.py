import unittest
from httplint import HttpResponseLinter
from httplint.cache import (
    FRESHNESS_FRESH,
    FRESHNESS_SHARED_PRIVATE,
    FRESHNESS_STALE_CACHE,
    FRESHNESS_STALE_ALREADY,
    FRESHNESS_HEURISTIC,
    FRESHNESS_NONE,
)


class TestCacheFreshness(unittest.TestCase):
    def test_same_freshness(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(
            [
                (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
                (b"Content-Type", b"text/plain"),
                (b"Content-Length", b"10"),
                (b"Cache-Control", b"max-age=60"),
            ]
        )
        linter.feed_content(b"1234567890")
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(FRESHNESS_FRESH, notes)
        self.assertNotIn(FRESHNESS_SHARED_PRIVATE, notes)

    def test_different_freshness_s_maxage(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(
            [
                (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
                (b"Content-Type", b"text/plain"),
                (b"Content-Length", b"10"),
                (b"Cache-Control", b"max-age=60, s-maxage=120"),
            ]
        )
        linter.feed_content(b"1234567890")
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(FRESHNESS_SHARED_PRIVATE, notes)
        self.assertNotIn(FRESHNESS_FRESH, notes)

    def test_different_freshness_private(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(
            [
                (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
                (b"Content-Type", b"text/plain"),
                (b"Content-Length", b"10"),
                (b"Cache-Control", b"private, max-age=60"),
            ]
        )
        linter.feed_content(b"1234567890")
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(FRESHNESS_FRESH, notes)
        self.assertNotIn(FRESHNESS_SHARED_PRIVATE, notes)

    def test_private_stale_shared_fresh(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(
            [
                (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
                (b"Content-Type", b"text/plain"),
                (b"Content-Length", b"10"),
                (b"Cache-Control", b"max-age=0, s-maxage=60"),
            ]
        )
        linter.feed_content(b"1234567890")
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(FRESHNESS_SHARED_PRIVATE, notes)
        self.assertNotIn(FRESHNESS_FRESH, notes)
        self.assertNotIn(FRESHNESS_STALE_ALREADY, notes)


if __name__ == "__main__":
    unittest.main()
