import unittest
from httplint import HttpResponseLinter
from httplint.status import HEADER_SHOULD_NOT_BE_IN_304


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
        linter.related = (
            HttpResponseLinter()
        )  # Hack to satisfy type checker if needed, but we need HttpRequestLinter
        # Better:
        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.related = req

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
        linter.related = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_416_WITHOUT_RANGE, notes)

    def test_417_no_expect(self):
        from httplint.status import STATUS_417_WITHOUT_EXPECT

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"417", b"Expectation Failed")
        linter.process_headers([(b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT")])

        from httplint.message import HttpRequestLinter

        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        req.process_headers([])
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

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
        linter.related = req

        linter.finish_content(True)
        notes = [n.__class__ for n in linter.notes]
        self.assertIn(STATUS_417_WITH_100_CONTINUE, notes)
        self.assertNotIn(STATUS_EXPECTATION_FAILED, notes)


if __name__ == "__main__":
    unittest.main()
