import unittest
import brotli
from httplint.message import HttpResponseLinter
from httplint.content_encoding import BAD_BROTLI, BAD_GZIP

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

    @staticmethod
    def _gzip_linter():
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Content-Encoding", b"gzip")])
        return linter

    def test_gzip_unterminated_fname_bounded(self):
        import time
        linter = self._gzip_linter()
        start = time.monotonic()
        linter.feed_content(b"\x1f\x8b\x08\x08" + b"\0" * 6)
        for _ in range(2048):
            linter.feed_content(b"A" * 1024)
        self.assertLess(time.monotonic() - start, 5)
        bad = [n for n in linter.notes if isinstance(n, BAD_GZIP)]
        self.assertEqual(len(bad), 1)

    def test_gzip_unterminated_fcomment_bytewise(self):
        import time
        linter = self._gzip_linter()
        start = time.monotonic()
        linter.feed_content(b"\x1f\x8b\x08\x10" + b"\0" * 6)
        for _ in range(200 * 1024):
            linter.feed_content(b"A")
        self.assertLess(time.monotonic() - start, 5)
        self.assertTrue(any(isinstance(n, BAD_GZIP) for n in linter.notes))

    def test_gzip_header_fields_bytewise(self):
        import gzip
        import hashlib
        import io
        data = b"Hello, header fields!"
        buf = io.BytesIO()
        with gzip.GzipFile(filename="a.txt", fileobj=buf, mode="wb") as f:
            f.write(data)
        raw = buf.getvalue()
        self.assertTrue(raw[3] & 8)
        linter = self._gzip_linter()
        for i in range(len(raw)):
            linter.feed_content(raw[i : i + 1])
        linter.finish_content(True)
        self.assertEqual(linter.decoded.hash, hashlib.md5(data).digest())
        self.assertFalse(any(isinstance(n, BAD_GZIP) for n in linter.notes))

    def test_gzip_max_extra_field(self):
        import hashlib
        import zlib
        data = b"payload"
        comp = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        body = comp.compress(data) + comp.flush()
        extra = b"\xff\xff" + b"x" * 65535
        raw = b"\x1f\x8b\x08\x04" + b"\0" * 6 + extra + body
        raw += zlib.crc32(data).to_bytes(4, "little") + len(data).to_bytes(4, "little")
        linter = self._gzip_linter()
        for i in range(0, len(raw), 1000):
            linter.feed_content(raw[i : i + 1000])
        linter.finish_content(True)
        self.assertFalse(any(isinstance(n, BAD_GZIP) for n in linter.notes))
        self.assertEqual(linter.decoded.hash, hashlib.md5(data).digest())

    def test_gzip_truncated_header_no_note(self):
        linter = self._gzip_linter()
        linter.feed_content(b"\x1f\x8b\x08\x08" + b"\0" * 6 + b"name")
        linter.finish_content(True)
        self.assertFalse(any(isinstance(n, BAD_GZIP) for n in linter.notes))

if __name__ == "__main__":
    unittest.main()
