import unittest
from httplint import HttpResponseLinter
from httplint.cache import (
    FRESHNESS_FRESH,
    FRESHNESS_SHARED_PRIVATE,
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

    def _expires_notes(self, headers):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(headers)
        linter.feed_content(b"hi")
        linter.finish_content(True)
        return [n.__class__ for n in linter.notes]

    def test_expires_without_start_time_is_explicit(self):
        # No start_time is set, so the lifetime comes from Expires - Date.
        notes = self._expires_notes([
            (b"Date", b"Mon, 20 Oct 2025 00:00:00 GMT"),
            (b"Expires", b"Tue, 21 Oct 2025 00:00:00 GMT"),
            (b"Content-Length", b"2"),
        ])
        self.assertNotIn(FRESHNESS_HEURISTIC, notes)
        self.assertIn(FRESHNESS_FRESH, notes)

    def test_expires_without_date_or_start_time_is_not_heuristic(self):
        notes = self._expires_notes([
            (b"Expires", b"Tue, 21 Oct 2025 00:00:00 GMT"),
            (b"Content-Length", b"2"),
        ])
        self.assertNotIn(FRESHNESS_HEURISTIC, notes)
        self.assertNotIn(FRESHNESS_FRESH, notes)
        self.assertNotIn(FRESHNESS_STALE_ALREADY, notes)

    def test_invalid_expires_without_clock_is_already_stale(self):
        notes = self._expires_notes([
            (b"Expires", b"0"),
            (b"Content-Length", b"2"),
        ])
        self.assertIn(FRESHNESS_STALE_ALREADY, notes)
        self.assertNotIn(FRESHNESS_HEURISTIC, notes)

    def test_invalid_expires_with_date_is_already_stale(self):
        notes = self._expires_notes([
            (b"Date", b"Mon, 20 Oct 2025 00:00:00 GMT"),
            (b"Expires", b"0"),
            (b"Content-Length", b"2"),
        ])
        self.assertIn(FRESHNESS_STALE_ALREADY, notes)

    def test_expires_with_s_maxage_leaves_private_lifetime_unknown(self):
        notes = self._expires_notes([
            (b"Expires", b"Tue, 21 Oct 2025 00:00:00 GMT"),
            (b"Cache-Control", b"s-maxage=5"),
            (b"Content-Length", b"2"),
        ])
        self.assertNotIn(FRESHNESS_HEURISTIC, notes)
        self.assertNotIn(FRESHNESS_SHARED_PRIVATE, notes)
        self.assertNotIn(FRESHNESS_STALE_ALREADY, notes)

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


class TestExpiresStorable(unittest.TestCase):
    def notes_for(self, expires):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"404", b"Not Found")
        linter.process_headers(
            [
                (b"Date", b"Tue, 15 Nov 1994 08:12:31 GMT"),
                (b"Expires", expires),
            ]
        )
        linter.finish_content(True)
        return [n.__class__ for n in linter.notes]

    def test_epoch_expires_makes_storable(self):
        from httplint.cache import STORE_STORABLE, STORE_UNSTORABLE

        notes = self.notes_for(b"Thu, 01 Jan 1970 00:00:00 GMT")
        self.assertIn(STORE_STORABLE, notes)
        self.assertNotIn(STORE_UNSTORABLE, notes)

    def test_expires_makes_storable(self):
        from httplint.cache import STORE_STORABLE, STORE_UNSTORABLE

        notes = self.notes_for(b"Fri, 01 Jan 1971 00:00:00 GMT")
        self.assertIn(STORE_STORABLE, notes)
        self.assertNotIn(STORE_UNSTORABLE, notes)

    def test_bad_expires_is_unstorable(self):
        from httplint.cache import STORE_STORABLE, STORE_UNSTORABLE

        notes = self.notes_for(b"nonsense")
        self.assertIn(STORE_UNSTORABLE, notes)
        self.assertNotIn(STORE_STORABLE, notes)


class TestEpochDates(unittest.TestCase):
    def check(self, headers, start_time):
        linter = HttpResponseLinter()
        linter.start_time = start_time
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(headers)
        linter.finish_content(True)
        return linter

    def test_epoch_date_gives_apparent_age(self):
        from httplint.cache import CURRENT_AGE

        linter = self.check(
            [
                (b"Date", b"Thu, 01 Jan 1970 00:00:00 GMT"),
                (b"Expires", b"Thu, 01 Jan 1970 01:00:00 GMT"),
            ],
            1800,
        )
        self.assertEqual(linter.caching.age, 1800)
        self.assertEqual(linter.caching.freshness_lifetime_private, 3600)
        self.assertIn(CURRENT_AGE, [n.__class__ for n in linter.notes])

    def test_epoch_expires_is_a_timestamp(self):
        linter = self.check(
            [
                (b"Date", b"Thu, 01 Jan 1970 00:16:40 GMT"),
                (b"Expires", b"Thu, 01 Jan 1970 00:00:00 GMT"),
            ],
            1000,
        )
        self.assertEqual(linter.caching.freshness_lifetime_private, -1000)
        self.assertIn(FRESHNESS_STALE_ALREADY, [n.__class__ for n in linter.notes])

    def test_invalid_expires_is_stale(self):
        linter = self.check(
            [
                (b"Date", b"Thu, 01 Jan 1970 00:16:40 GMT"),
                (b"Expires", b"nonsense"),
            ],
            1000,
        )
        self.assertEqual(linter.caching.freshness_lifetime_private, -1000)
        self.assertIn(FRESHNESS_STALE_ALREADY, [n.__class__ for n in linter.notes])


if __name__ == "__main__":
    unittest.main()
