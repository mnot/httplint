import unittest
from httplint import HttpResponseLinter
from httplint.cache import (
    FRESHNESS_FRESH,
    FRESHNESS_SHARED_PRIVATE,
    FRESHNESS_STALE_CACHE,
    FRESHNESS_STALE_ALREADY,
    FRESHNESS_HEURISTIC,
    FRESHNESS_NONE,
    STALE_SERVABLE,
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

    def test_cc_and_expires(self):
        from httplint.cache import CC_AND_EXPIRES
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Cache-Control", b"max-age=60"),
            (b"Expires", b"Thu, 01 Dec 1994 16:00:00 GMT"),
            (b"Date", b"Thu, 01 Dec 1994 16:00:00 GMT"),
        ])
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(CC_AND_EXPIRES, notes)

    def test_stale_while_revalidate(self):
        from httplint.cache import STALE_WHILE_REVALIDATE
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
            (b"Cache-Control", b"max-age=60, stale-while-revalidate=120"),
        ])
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STALE_WHILE_REVALIDATE, notes)

    def test_stale_if_error(self):
        from httplint.cache import STALE_IF_ERROR
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
            (b"Cache-Control", b"max-age=60, stale-if-error=120"),
        ])
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STALE_IF_ERROR, notes)
        self.assertNotIn(STALE_SERVABLE, notes)

    def test_stale_extensions(self):
        from httplint.cache import STALE_WHILE_REVALIDATE, STALE_IF_ERROR
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
            (b"Cache-Control", b"max-age=60, stale-while-revalidate=120, stale-if-error=120"),
        ])
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STALE_WHILE_REVALIDATE, notes)
        self.assertIn(STALE_IF_ERROR, notes)


if __name__ == "__main__":
    unittest.main()
