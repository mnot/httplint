import unittest
import brotli
from httplint.message import HttpResponseLinter
from httplint.content_encoding import BAD_BROTLI

class TestContentEncoding(unittest.TestCase):
    def test_brotli_valid(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"br")])
        
        data = b"Hello, Brotli!"
        compressed = brotli.compress(data)
        
        linter.feed_content(compressed)
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertFalse(any(isinstance(n, BAD_BROTLI) for n in notes), "BAD_BROTLI should not be present")

    def test_brotli_corrupt(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"br")])
        
        compressed = b"Create some corrupt brotli data"
        
        linter.feed_content(compressed)
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertTrue(any(isinstance(n, BAD_BROTLI) for n in notes), "BAD_BROTLI should be present")

if __name__ == "__main__":
    unittest.main()
