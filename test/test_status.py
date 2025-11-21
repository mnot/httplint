import unittest
from httplint import HttpResponseLinter
from httplint.status import HEADER_SHOULD_NOT_BE_IN_304

class TestStatus304(unittest.TestCase):
    def test_304_prohibited_headers(self):
        for header in [b"Content-Type", b"Content-Encoding", b"Content-Language"]:
            linter = HttpResponseLinter()
            linter.process_response_topline(b"HTTP/1.1", b"304", b"Not Modified")
            linter.process_headers([
                (b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"),
                (header, b"foo")
            ])
            linter.finish_content(True)
            
            notes = [n.__class__ for n in linter.notes]
            self.assertIn(HEADER_SHOULD_NOT_BE_IN_304, notes)

    def test_304_allowed_headers(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"304", b"Not Modified")
        linter.process_headers([
            (b"Date", b"Fri, 01 Jan 2021 00:00:00 GMT"),
            (b"Cache-Control", b"max-age=60"),
            (b"Expires", b"Fri, 01 Jan 2021 00:01:00 GMT"),
            (b"ETag", b"12345"),
            (b"Vary", b"Accept-Encoding"),
            (b"Content-Location", b"/foo")
        ])
        linter.finish_content(True)
        
        notes = [n.__class__ for n in linter.notes]
        self.assertNotIn(HEADER_SHOULD_NOT_BE_IN_304, notes)

if __name__ == '__main__':
    unittest.main()
