import tracemalloc
import unittest
import brotli
from httplint.message import HttpResponseLinter
from httplint.content_encoding import BAD_BROTLI, DECOMPRESSION_LIMIT

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

    def test_brotli_bomb_bounded(self):
        # A few hundred bytes that expand to over 100MB must not be materialised in one piece.
        compressor = brotli.Compressor(quality=5, lgwin=24)
        parts = [compressor.process(b"\0" * (1024 * 1024)) for _ in range(110)]
        parts.append(compressor.finish())
        bomb = b"".join(parts)
        self.assertLess(len(bomb), 4096)

        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"br")])
        sizes = []
        linter.decoded.processors.append(lambda c: sizes.append(len(c)))

        tracemalloc.start()
        try:
            linter.feed_content(bomb)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        linter.finish_content(True)

        self.assertTrue(any(isinstance(n, DECOMPRESSION_LIMIT) for n in linter.notes))
        self.assertFalse(any(isinstance(n, BAD_BROTLI) for n in linter.notes))
        self.assertLess(max(sizes, default=0), 32 * 1024 * 1024)
        self.assertLess(peak, 16 * 1024 * 1024)

    def test_brotli_multi_chunk_roundtrip(self):
        data = bytes(range(256)) * 20000  # 5MB, spans several output pieces
        compressed = brotli.compress(data)
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"br")])
        for i in range(0, len(compressed), 1000):
            linter.feed_content(compressed[i : i + 1000])
        linter.finish_content(True)
        self.assertEqual(linter.decoded.length, len(data))
        self.assertFalse(any(isinstance(n, BAD_BROTLI) for n in linter.notes))

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
