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

    def test_gzip_valid(self):
        import gzip
        import hashlib
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"gzip")])
        
        data = b"Hello, Gzip!"
        compressed = gzip.compress(data)
        
        linter.feed_content(compressed)
        linter.finish_content(True)
        
        if linter.decoded.hash != hashlib.md5(data).digest():
            print(f"Notes: {[n.__class__.__name__ for n in linter.notes]}")
            # print(f"Sample: {linter.content_sample!r}")

        self.assertEqual(linter.decoded.hash, hashlib.md5(data).digest())

    def test_double_gzip(self):
        import gzip
        import hashlib
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"gzip, gzip")])
        
        data = b"Hello, Double Gzip!"
        once = gzip.compress(data)
        twice = gzip.compress(once)
        
        linter.feed_content(twice)
        linter.finish_content(True)
        
        if linter.decoded.hash != hashlib.md5(data).digest():
             print(f"Double Gzip Notes: {[n.__class__.__name__ for n in linter.notes]}")

        self.assertEqual(linter.decoded.hash, hashlib.md5(data).digest())

if __name__ == "__main__":
    unittest.main()
