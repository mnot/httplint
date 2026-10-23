import tracemalloc
import unittest
import brotli
from httplint.message import HttpResponseLinter
import zlib
from httplint.charset import CHARSET_UNDECODABLE
from httplint.content_encoding import BAD_BROTLI, BAD_DEFLATE, BAD_GZIP, DECOMPRESSION_LIMIT
from httplint.content_type import CONTENT_TYPE_MISMATCH
from httplint.message import CL_CORRECT, CONTENT_NOT_ALLOWED

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


def _has(linter, note_class):
    return any(isinstance(n, note_class) for n in linter.notes)


def _response(status, headers, chunks, method_head=False):
    linter = HttpResponseLinter()
    linter.is_head_response = method_head
    linter.process_response_topline(b"HTTP/1.1", status, b"Phrase")
    linter.process_headers(headers)
    for chunk in chunks:
        linter.feed_content(chunk)
    linter.finish_content(True)
    return linter


LATIN1_HTML = b"<html><body>" + "h\u00e9llo ".encode("latin-1") * 200 + b"</body></html>"
HTML_UTF8 = [(b"Content-Type", b"text/html; charset=utf-8")]


class TestCanHaveContent(unittest.TestCase):
    def test_status_table(self):
        for status in (100, 101, 150, 199, 204, 205, 304):
            linter = HttpResponseLinter()
            linter.process_response_topline(b"HTTP/1.1", str(status).encode(), b"x")
            self.assertFalse(linter.can_have_content(), status)
            self.assertFalse(linter.has_full_representation(), status)
        for status in (200, 201, 206, 301, 404, 500):
            linter = HttpResponseLinter()
            linter.process_response_topline(b"HTTP/1.1", str(status).encode(), b"x")
            self.assertTrue(linter.can_have_content(), status)
            self.assertEqual(linter.has_full_representation(), status != 206, status)

    def test_head_and_nonnumeric(self):
        linter = HttpResponseLinter()
        linter.is_head_response = True
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        self.assertFalse(linter.can_have_content())
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"abc", b"OK")
        self.assertTrue(linter.can_have_content())

    def test_204_with_content(self):
        for status in (b"100", b"101", b"199", b"204", b"205", b"304"):
            linter = _response(status, [(b"Content-Length", b"5")], [b"hello"])
            self.assertTrue(_has(linter, CONTENT_NOT_ALLOWED), status)
            self.assertFalse(_has(linter, CL_CORRECT), status)

    def test_204_without_content(self):
        linter = _response(b"204", [], [])
        self.assertFalse(_has(linter, CONTENT_NOT_ALLOWED))

    def test_200_still_checked(self):
        linter = _response(b"200", [(b"Content-Length", b"5")], [b"hello"])
        self.assertTrue(_has(linter, CL_CORRECT))
        self.assertFalse(_has(linter, CONTENT_NOT_ALLOWED))

    def test_206_has_content_but_no_content_checks(self):
        headers = HTML_UTF8 + [(b"Content-Length", str(len(LATIN1_HTML)).encode())]
        linter = _response(b"206", headers, [LATIN1_HTML])
        self.assertFalse(_has(linter, CONTENT_NOT_ALLOWED))
        self.assertTrue(_has(linter, CL_CORRECT))
        self.assertFalse(_has(linter, CHARSET_UNDECODABLE))

    def test_199_skips_content_checks(self):
        # The old status list was range(100, 199), which missed 199.
        linter = _response(b"199", HTML_UTF8, [LATIN1_HTML])
        self.assertFalse(_has(linter, CHARSET_UNDECODABLE))
        self.assertFalse(_has(linter, CONTENT_TYPE_MISMATCH))


class TestUndecodedCodings(unittest.TestCase):
    def test_control_without_coding(self):
        linter = _response(b"200", HTML_UTF8, [LATIN1_HTML])
        self.assertTrue(_has(linter, CHARSET_UNDECODABLE))

    def test_deflate_zlib(self):
        linter = _response(
            b"200", HTML_UTF8 + [(b"Content-Encoding", b"deflate")], [zlib.compress(LATIN1_HTML)]
        )
        self.assertEqual(linter.decoded.length, len(LATIN1_HTML))
        self.assertEqual(linter.content_sample, LATIN1_HTML[:8192])
        self.assertFalse(_has(linter, BAD_DEFLATE))
        # decoded properly, so the real content problem is still found
        self.assertTrue(_has(linter, CHARSET_UNDECODABLE))

    def test_deflate_raw(self):
        comp = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw = comp.compress(LATIN1_HTML) + comp.flush()
        linter = _response(b"200", [(b"Content-Encoding", b"deflate")], [raw])
        self.assertEqual(linter.decoded.length, len(LATIN1_HTML))
        self.assertFalse(_has(linter, BAD_DEFLATE))

    def test_deflate_chunking(self):
        data = bytes(range(256)) * 5000
        for compressed in (zlib.compress(data), zlib.compress(data)[2:-4]):
            for step in (1, 7, 1000, len(compressed)):
                chunks = [compressed[i : i + step] for i in range(0, len(compressed), step)]
                linter = _response(b"200", [(b"Content-Encoding", b"deflate")], chunks)
                self.assertEqual(linter.decoded.length, len(data), step)
                self.assertFalse(_has(linter, BAD_DEFLATE), step)

    def test_deflate_corrupt(self):
        linter = _response(
            b"200", [(b"Content-Encoding", b"deflate")], [b"\x78\x9c" + b"\xff" * 50]
        )
        self.assertTrue(_has(linter, BAD_DEFLATE))

    def test_deflate_then_gzip_order(self):
        import gzip

        data = b"hello world" * 100
        both = gzip.compress(zlib.compress(data))
        linter = _response(b"200", [(b"Content-Encoding", b"deflate, gzip")], [both])
        self.assertEqual(linter.decoded.length, len(data))

    def test_undecoded_codings_skip_content_checks(self):
        payloads = {
            b"zstd": b"\x28\xb5\x2f\xfd" + bytes(range(128, 256)) * 4,
            b"compress": b"\x1f\x9d\x90" + bytes(range(128, 256)) * 4,
            b"aes128gcm": bytes(range(128, 256)) * 4,
        }
        for coding, payload in payloads.items():
            headers = [(b"Content-Type", b"text/html; charset=utf-8"), (b"Content-Encoding", coding)]
            linter = _response(b"200", headers, [payload])
            self.assertFalse(linter.content_decoded, coding)
            self.assertEqual(linter.content_sample, b"", coding)
            self.assertFalse(_has(linter, CHARSET_UNDECODABLE), coding)
            self.assertFalse(_has(linter, CONTENT_TYPE_MISMATCH), coding)

    def test_undecoded_coding_skips_content_type_mismatch(self):
        headers = [(b"Content-Type", b"image/png"), (b"Content-Encoding", b"zstd")]
        linter = _response(b"200", headers, [b"\x28\xb5\x2f\xfd not a png"])
        self.assertFalse(_has(linter, CONTENT_TYPE_MISMATCH))
        # same body with no coding is a mismatch
        linter = _response(b"200", [(b"Content-Type", b"image/png")], [b"not a png"])
        self.assertTrue(_has(linter, CONTENT_TYPE_MISMATCH))

    def test_undecoded_hidden_behind_decodable(self):
        # "zstd, gzip": gzip is undone, leaving zstd bytes
        import gzip

        headers = HTML_UTF8 + [(b"Content-Encoding", b"zstd, gzip")]
        linter = _response(b"200", headers, [gzip.compress(LATIN1_HTML)])
        self.assertFalse(linter.content_decoded)
        self.assertFalse(_has(linter, CHARSET_UNDECODABLE))
        # "gzip, zstd": can't get past zstd to reach gzip
        headers = HTML_UTF8 + [(b"Content-Encoding", b"gzip, zstd")]
        linter = _response(b"200", headers, [b"\x28\xb5\x2f\xfd" + b"\xff" * 100])
        self.assertFalse(_has(linter, BAD_GZIP))
        self.assertFalse(_has(linter, CHARSET_UNDECODABLE))

    def test_identity_is_decoded(self):
        linter = _response(b"200", HTML_UTF8 + [(b"Content-Encoding", b"identity")], [LATIN1_HTML])
        self.assertTrue(linter.content_decoded)
        self.assertTrue(_has(linter, CHARSET_UNDECODABLE))


if __name__ == "__main__":
    unittest.main()
