import unittest
from httplint.message import HttpResponseLinter, CL_INCORRECT
from httplint.content_type import CONTENT_TYPE_MISMATCH

class TestNoContent(unittest.TestCase):
    def test_cl_incorrect_ignored(self):
        linter = HttpResponseLinter(no_content=True)
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Length", b"100")])
        linter.feed_content(b"") # 0 bytes
        linter.finish_content(True)

        self.assertFalse(any(n.__class__ == CL_INCORRECT for n in linter.notes))

    def test_cl_incorrect_normal(self):
        linter = HttpResponseLinter(no_content=False)
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Length", b"100")])
        linter.feed_content(b"") # 0 bytes
        linter.finish_content(True)

        self.assertTrue(any(n.__class__ == CL_INCORRECT for n in linter.notes))

    def test_content_type_mismatch_ignored(self):
        linter = HttpResponseLinter(no_content=True)
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Type", b"image/png")])
        linter.feed_content(b"not png")
        linter.finish_content(True)

        self.assertFalse(any(n.__class__ == CONTENT_TYPE_MISMATCH for n in linter.notes))

    def test_content_type_mismatch_normal(self):
        linter = HttpResponseLinter(no_content=False)
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Type", b"image/png")])
        linter.feed_content(b"not png")
        linter.finish_content(True)

        self.assertTrue(any(n.__class__ == CONTENT_TYPE_MISMATCH for n in linter.notes))

if __name__ == "__main__":
    unittest.main()
