import tracemalloc
import unittest
import brotli
from httplint.message import HttpResponseLinter
from httplint.content_encoding import BAD_BROTLI, BAD_GZIP, DECOMPRESSION_LIMIT

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

    def test_gzip_header_cap_independent_of_chunking(self):
        import hashlib
        import zlib
        from httplint.content_encoding import MAX_GZIP_HEADER_BYTES

        data = b"payload"
        comp = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        body = comp.compress(data) + comp.flush()
        trailer = zlib.crc32(data).to_bytes(4, "little") + len(data).to_bytes(4, "little")

        def stream(header_len, flags):
            # header_len covers the fixed 10 bytes plus the fields built below
            if flags == "extra_name_comment":
                extra = b"\xff\xff" + b"x" * 65535
                rest = header_len - 10 - len(extra)
                name = b"n" * (rest // 2) + b"\0"
                comment = b"c" * (rest - len(name) - 1) + b"\0"
                hdr = b"\x1f\x8b\x08\x1c" + b"\0" * 6 + extra + name + comment
            else:
                hdr = b"\x1f\x8b\x08\x08" + b"\0" * 6 + b"n" * (header_len - 11) + b"\0"
            self.assertEqual(len(hdr), header_len)
            return hdr + body + trailer

        for flags in ("name", "extra_name_comment"):
            for delta, valid in ((0, True), (1, False)):
                raw = stream(MAX_GZIP_HEADER_BYTES + delta, flags)
                for step in (1, 1000, 100000, len(raw)):
                    linter = self._gzip_linter()
                    for i in range(0, len(raw), step):
                        linter.feed_content(raw[i : i + step])
                    linter.finish_content(True)
                    bad = any(isinstance(n, BAD_GZIP) for n in linter.notes)
                    self.assertEqual(bad, not valid, (flags, delta, step))
                    if valid:
                        self.assertEqual(linter.decoded.hash, hashlib.md5(data).digest())

    def test_gzip_truncated_header_no_note(self):
        linter = self._gzip_linter()
        linter.feed_content(b"\x1f\x8b\x08\x08" + b"\0" * 6 + b"name")
        linter.finish_content(True)
        self.assertFalse(any(isinstance(n, BAD_GZIP) for n in linter.notes))

if __name__ == "__main__":
    unittest.main()
