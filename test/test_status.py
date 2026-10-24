import unittest
from httplint import HttpResponseLinter
from httplint.message import STATUS_CODE_NON_NUMERIC
from httplint.status import (
    CONNECT_TUNNEL_FRAMING,
    HEADER_SHOULD_NOT_BE_IN_304,
    STATUS_NONSTANDARD,
)


class TestStatus304(unittest.TestCase):
    def test_304_prohibited_headers(self):
        for header in [b"Content-Type", b"Content-Encoding", b"Content-Language"]:
            linter = HttpResponseLinter()
            linter.process_response_topline(b"HTTP/1.1", b"304", b"Not Modified")
            linter.process_headers(
                [(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"), (header, b"foo")]
            )
            linter.finish_content(True)

            notes = [n.__class__ for n in linter.notes]
            self.assertIn(HEADER_SHOULD_NOT_BE_IN_304, notes)

    def test_304_allowed_headers(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"304", b"Not Modified")
        linter.process_headers(
            [
                (b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"),
                (b"Cache-Control", b"max-age=60"),
                (b"Expires", b"Fri, 01 Jan 2021 00:01:00 GMT"),
                (b"ETag", b"12345"),
                (b"Vary", b"Accept-Encoding"),
                (b"Content-Location", b"/foo"),
            ]
        )
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertNotIn(HEADER_SHOULD_NOT_BE_IN_304, notes)


class TestStatus4xx(unittest.TestCase):
    def test_412_no_precondition(self):
        from httplint.status import STATUS_412_WITHOUT_PRECONDITION

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"412", b"Precondition Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        # Mock request
        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_412_WITHOUT_PRECONDITION, notes)

    def test_416_no_range(self):
        from httplint.status import STATUS_416_WITHOUT_RANGE

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"416", b"Range Not Satisfiable")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_416_WITHOUT_RANGE, notes)

    @staticmethod
    def _lint_416(request_headers, response_headers, method=b"GET", with_request=True):
        return [
            n.__class__
            for n in TestStatus4xx._notes_416(
                request_headers, response_headers, method, with_request
            )
        ]

    @staticmethod
    def _notes_416(request_headers, response_headers, method=b"GET", with_request=True):
        from httplint.message import HttpRequestLinter

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"416", b"Range Not Satisfiable")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")] + response_headers)
        if with_request:
            req = HttpRequestLinter()
            req.process_request_topline(method, b"/", b"HTTP/1.1")
            req.process_headers(request_headers)
            linter.request = req
        linter.finish_content(True)
        return list(linter.notes)

    def test_416_missing_content_range(self):
        from httplint.status import STATUS_416_WITHOUT_CONTENT_RANGE

        for rng in (
            b"bytes=0-1",
            b"bytes=100-200",
            b"BYTES=100-200",
            b"bytes=0-1,5-6",
            b"bytes=-5",
        ):
            with self.subTest(rng=rng):
                notes = self._lint_416([(b"Range", rng)], [])
                self.assertIn(STATUS_416_WITHOUT_CONTENT_RANGE, notes)

    def test_416_missing_content_range_subject(self):
        from httplint.status import STATUS_416_WITHOUT_CONTENT_RANGE

        notes = self._notes_416([(b"Range", b"bytes=100-200")], [])
        subjects = [n.subject for n in notes if isinstance(n, STATUS_416_WITHOUT_CONTENT_RANGE)]
        self.assertEqual(subjects, ["field-content-range"])

    def test_416_missing_content_range_level(self):
        from httplint.note import levels
        from httplint.status import STATUS_416_WITHOUT_CONTENT_RANGE

        self.assertEqual(STATUS_416_WITHOUT_CONTENT_RANGE.level, levels.WARN)

    def test_416_content_range_present(self):
        from httplint.status import STATUS_416_WITHOUT_CONTENT_RANGE

        for value in (b"bytes */10", b"bytes 0-5/10", b"garbage"):
            with self.subTest(value=value):
                notes = self._lint_416([(b"Range", b"bytes=100-200")], [(b"Content-Range", value)])
                self.assertNotIn(STATUS_416_WITHOUT_CONTENT_RANGE, notes)

    def test_416_missing_content_range_not_flagged_unless_bytes_range(self):
        from httplint.status import STATUS_416_WITHOUT_CONTENT_RANGE

        # Guards: other range units, no Range header, and no known request.
        for rng in (b"items=1-2", b"garbage", b"bytes"):
            with self.subTest(rng=rng):
                notes = self._lint_416([(b"Range", rng)], [])
                self.assertNotIn(STATUS_416_WITHOUT_CONTENT_RANGE, notes)
        notes = self._lint_416([], [])
        self.assertNotIn(STATUS_416_WITHOUT_CONTENT_RANGE, notes)
        notes = self._lint_416([], [], with_request=False)
        self.assertNotIn(STATUS_416_WITHOUT_CONTENT_RANGE, notes)

    def test_417_no_expect(self):
        from httplint.status import STATUS_417_WITHOUT_EXPECT

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_417_WITHOUT_EXPECT, notes)

    def test_417_with_100_continue(self):
        from httplint.status import STATUS_417_WITH_100_CONTINUE

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([(b"Expect", b"100-continue")])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_417_WITH_100_CONTINUE, notes)

    def test_406_no_negotiation(self):
        from httplint.status import STATUS_406_WITHOUT_NEGOTIATION

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"406", b"Not Acceptable")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_406_WITHOUT_NEGOTIATION, notes)

    def test_406_with_negotiation(self):
        from httplint.status import STATUS_406_WITHOUT_NEGOTIATION

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"406", b"Not Acceptable")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([(b"Accept", b"text/html")])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertNotIn(STATUS_406_WITHOUT_NEGOTIATION, notes)


class TestStatus405(unittest.TestCase):
    def test_405_method_in_allow(self):
        from httplint.status import STATUS_405_METHOD_IN_ALLOW, STATUS_METHOD_NOT_ALLOWED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"405", b"Method Not Allowed")
        linter.process_headers(
            [(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"), (b"Allow", b"GET, HEAD")]
        )

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_405_METHOD_IN_ALLOW, notes)
        self.assertNotIn(STATUS_METHOD_NOT_ALLOWED, notes)

    def test_405_method_not_in_allow(self):
        from httplint.status import STATUS_405_METHOD_IN_ALLOW, STATUS_METHOD_NOT_ALLOWED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"405", b"Method Not Allowed")
        linter.process_headers(
            [(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"), (b"Allow", b"POST, PUT")]
        )

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertNotIn(STATUS_405_METHOD_IN_ALLOW, notes)
        self.assertIn(STATUS_METHOD_NOT_ALLOWED, notes)

    def test_405_no_allow(self):
        from httplint.status import STATUS_405_METHOD_IN_ALLOW, STATUS_METHOD_NOT_ALLOWED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"405", b"Method Not Allowed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertNotIn(STATUS_405_METHOD_IN_ALLOW, notes)
        self.assertIn(STATUS_METHOD_NOT_ALLOWED, notes)


class TestStatus412(unittest.TestCase):
    def test_412_generic(self):
        from httplint.status import STATUS_PRECONDITION_FAILED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"412", b"Precondition Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([(b"If-Match", b'"123"')])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_PRECONDITION_FAILED, notes)

    def test_412_without_precondition(self):
        from httplint.status import (
            STATUS_412_WITHOUT_PRECONDITION,
            STATUS_PRECONDITION_FAILED,
        )

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"412", b"Precondition Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_412_WITHOUT_PRECONDITION, notes)
        self.assertNotIn(STATUS_PRECONDITION_FAILED, notes)


class TestStatus417(unittest.TestCase):
    def test_417_generic(self):
        from httplint.status import STATUS_EXPECTATION_FAILED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([(b"Expect", b"foo")])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_EXPECTATION_FAILED, notes)

    def test_417_without_expect(self):
        from httplint.status import STATUS_417_WITHOUT_EXPECT, STATUS_EXPECTATION_FAILED

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_417_WITHOUT_EXPECT, notes)
        self.assertNotIn(STATUS_EXPECTATION_FAILED, notes)

    def test_417_with_100_continue(self):
        from httplint.status import (
            STATUS_417_WITH_100_CONTINUE,
            STATUS_EXPECTATION_FAILED,
        )

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([(b"Expect", b"100-continue")])
        linter.request = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_417_WITH_100_CONTINUE, notes)
        self.assertNotIn(STATUS_EXPECTATION_FAILED, notes)


class TestStatusCodeSyntax(unittest.TestCase):
    """The status code must be exactly three ASCII digits (RFC 9112 section 4)."""

    def _lint(self, status_code: bytes) -> HttpResponseLinter:
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", status_code, b"OK")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])
        linter.finish_content(True)
        return linter

    def test_invalid_status_code_syntax(self):
        for raw in [
            b"2_00",
            b"+200",
            b" 200",
            b"200 ",
            b"0200",
            b"-1",
            b"20",
            b"",
            b"abc",
            b"\xd9\xa2\xd9\xa0\xd9\xa0",  # Arabic-Indic digits
        ]:
            with self.subTest(raw=raw):
                linter = self._lint(raw)
                self.assertIsNone(linter.status_code)
                self.assertEqual(linter.status_code_str, raw.decode("ascii", "replace"))
                self.assertIn(STATUS_CODE_NON_NUMERIC, [n.__class__ for n in linter.notes])

    def test_invalid_status_code_only_one_status_note(self):
        for raw in [b"+200", b"0200", b"abc"]:
            with self.subTest(raw=raw):
                classes = [n.__class__ for n in self._lint(raw).notes]
                self.assertIn(STATUS_CODE_NON_NUMERIC, classes)
                self.assertNotIn(STATUS_NONSTANDARD, classes)

    def test_invalid_status_code_with_status_dependent_fields(self):
        from httplint.field.parsers.content_range import CONTENT_RANGE_MEANINGLESS
        from httplint.field.parsers.location import LOCATION_UNDEFINED
        from httplint.field.parsers.strict_transport_security import HSTS_OVER_HTTP

        linter = HttpResponseLinter()
        linter.base_uri = "http://example.com/"
        linter.process_response_topline(b"HTTP/1.1", b"+200", b"OK")
        linter.process_headers(
            [
                (b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"),
                (b"Location", b"/foo"),
                (b"Content-Range", b"bytes 0-9/10"),
                (b"Strict-Transport-Security", b"max-age=31536000"),
            ]
        )
        linter.finish_content(True)
        classes = [n.__class__ for n in linter.notes]
        for n in linter.notes:  # HSTS_OVER_HTTP is a child of HSTS_INVALID
            classes.extend(sub.__class__ for sub in n.subnotes)
        self.assertIsNone(linter.status_code)
        for note in [LOCATION_UNDEFINED, CONTENT_RANGE_MEANINGLESS, HSTS_OVER_HTTP]:
            self.assertIn(note, classes)

    def test_valid_status_code_syntax(self):
        linter = self._lint(b"200")
        self.assertEqual(linter.status_code, 200)
        self.assertEqual(linter.status_code_str, "200")
        self.assertNotIn(STATUS_CODE_NON_NUMERIC, [n.__class__ for n in linter.notes])

    def test_out_of_range_three_digit_codes_unchanged(self):
        for raw, number in [(b"099", 99), (b"600", 600), (b"999", 999)]:
            with self.subTest(raw=raw):
                linter = self._lint(raw)
                self.assertEqual(linter.status_code, number)
                self.assertEqual(linter.status_code_str, raw.decode("ascii"))
                classes = [n.__class__ for n in linter.notes]
                self.assertNotIn(STATUS_CODE_NON_NUMERIC, classes)
                self.assertIn(STATUS_NONSTANDARD, classes)


class TestStatus206(unittest.TestCase):
    @staticmethod
    def _notes_206(response_headers):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"206", b"Partial Content")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")] + response_headers)
        linter.finish_content(True)
        return list(linter.notes)

    def test_206_without_content_range_subject(self):
        from httplint.status import PARTIAL_WITHOUT_RANGE

        notes = self._notes_206([])
        subjects = [n.subject for n in notes if isinstance(n, PARTIAL_WITHOUT_RANGE)]
        self.assertEqual(subjects, ["field-content-range"])

    def test_206_with_content_range_not_flagged(self):
        # Guard
        from httplint.status import PARTIAL_WITHOUT_RANGE

        notes = self._notes_206([(b"Content-Range", b"bytes 0-4/10")])
        self.assertFalse(any(isinstance(n, PARTIAL_WITHOUT_RANGE) for n in notes))


class TestStatusConnectTunnel(unittest.TestCase):
    @staticmethod
    def _notes(status, response_headers, method=b"CONNECT", with_request=True):
        from httplint.message import HttpRequestLinter

        linter = HttpResponseLinter()
        if with_request:
            req = HttpRequestLinter()
            req.process_request_topline(method, b"example.com:443", b"HTTP/1.1")
            req.process_headers([])
            linter.request = req
        linter.process_response_topline(b"HTTP/1.1", status, b"Phrase")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")] + response_headers)
        linter.finish_content(True)
        return [n for n in linter.notes if isinstance(n, CONNECT_TUNNEL_FRAMING)]

    def test_connect_2xx_with_framing_headers(self):
        for status in (b"200", b"204", b"299"):
            for name in (b"Content-Length", b"content-length", b"Transfer-Encoding"):
                with self.subTest(status=status, name=name):
                    notes = self._notes(status, [(name, b"0" if b"ength" in name else b"chunked")])
                    self.assertEqual([n.subject for n in notes], ["field-" + name.decode().lower()])

    def test_connect_2xx_with_both_headers(self):
        notes = self._notes(b"200", [(b"Content-Length", b"0"), (b"Transfer-Encoding", b"chunked")])
        self.assertEqual(
            sorted(n.subject for n in notes), ["field-content-length", "field-transfer-encoding"]
        )

    def test_connect_2xx_with_invalid_header_value(self):
        notes = self._notes(b"200", [(b"Content-Length", b"abc")])
        self.assertEqual(len(notes), 1)

    def test_connect_note_level(self):
        from httplint.note import levels

        self.assertEqual(CONNECT_TUNNEL_FRAMING.level, levels.BAD)

    def test_connect_2xx_without_framing_headers(self):
        # Guard
        self.assertEqual(self._notes(b"200", []), [])

    def test_connect_non_2xx_not_flagged(self):
        # Guard
        for status in (b"407", b"502"):
            self.assertEqual(self._notes(status, [(b"Content-Length", b"0")]), [], status)

    def test_non_connect_request_not_flagged(self):
        # Guard
        self.assertEqual(self._notes(b"200", [(b"Content-Length", b"0")], method=b"GET"), [])

    def test_no_request_not_flagged(self):
        # Guard
        notes = self._notes(b"200", [(b"Content-Length", b"0")], with_request=False)
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
