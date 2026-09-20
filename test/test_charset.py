import unittest

from httplint.charset import (
    CHARSET_IMPLICIT_MISMATCH,
    CHARSET_MISMATCH,
    CHARSET_UNDECODABLE,
    _decode_declared,
    _encodings_compatible,
    _sample_is_truncated,
)
from httplint.content_encoding import BAD_ZLIB
from httplint.message import HttpResponseLinter


def _run(headers, body, complete=True, extra_notes=()):
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(headers + [(b"Content-Length", str(len(body)).encode())])
    linter.feed_content(body)
    for note_cls, note_kwargs in extra_notes:
        linter.notes.add("field-content-encoding", note_cls, **note_kwargs)
    linter.finish_content(complete)
    return linter


class _FakeLinter:
    """Minimal stand-in for the attributes _sample_is_truncated reads."""

    def __init__(self, content_sample_truncated=False, complete=True, notes=()):
        self.content_sample_truncated = content_sample_truncated
        self.complete = complete
        self.notes = list(notes)


def _has_note(notes, cls):
    return any(isinstance(n, cls) for n in notes)


class CharsetTest(unittest.TestCase):
    def test_no_charset_no_note(self):
        body = "Hello world! Café and résumé.".encode("utf-8")
        linter = _run([(b"Content-Type", b"text/plain")], body)
        self.assertFalse(_has_note(linter.notes, CHARSET_MISMATCH))
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_pure_ascii_no_note(self):
        body = b"Hello world, this is plain ASCII text only."
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
        )
        self.assertFalse(_has_note(linter.notes, CHARSET_MISMATCH))

    def test_utf8_matches_declared(self):
        body = ("Café résumé naïve " * 50).encode("utf-8")
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
        )
        self.assertFalse(_has_note(linter.notes, CHARSET_MISMATCH))
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_utf8_declared_but_latin1_content(self):
        body = ("Café résumé naïve garçon " * 80).encode("latin-1")
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
        )
        # latin-1 bytes (0xE9 etc.) are not valid utf-8 continuation bytes
        self.assertTrue(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_json_implicit_utf8_mismatch(self):
        body = '{"name": "Café résumé"}'.encode("latin-1") * 30
        linter = _run([(b"Content-Type", b"application/json")], body)
        self.assertTrue(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_json_ascii_ok(self):
        body = b'{"name": "value"}' * 20
        linter = _run([(b"Content-Type", b"application/json")], body)
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))
        self.assertFalse(_has_note(linter.notes, CHARSET_IMPLICIT_MISMATCH))

    def test_mismatch_decodable_but_wrong(self):
        # Russian text in windows-1251. Declaring iso-8859-1 "works"
        # (latin-1 decodes any byte) but produces gibberish.
        russian = (
            "Привет мир! "
            "Это длинный русский текст для проверки определения кодировки. "
            "Москва Санкт-Петербург Новосибирск Екатеринбург Казань. "
            "Литература наука культура история философия. "
        ) * 50
        body = russian.encode("windows-1251")
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=iso-8859-1")],
            body,
        )
        self.assertTrue(_has_note(linter.notes, CHARSET_MISMATCH))

    def test_plus_json_requires_utf8(self):
        # +json subtypes inherit JSON's UTF-8 requirement per RFC 8259.
        body = '{"name": "Café résumé"}'.encode("latin-1") * 30
        linter = _run([(b"Content-Type", b"application/vnd.api+json")], body)
        self.assertTrue(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_multibyte_char_split_at_sample_boundary(self):
        # Regression for #155: a multi-byte character straddling the fixed
        # 8192-byte content_sample cutoff must not be reported as
        # undecodable when the full content is valid. Built so byte 8191
        # is deliberately the lead byte of a 2-byte UTF-8 sequence, so the
        # split is guaranteed rather than incidental.
        lead_byte_offset = 8191
        body = b"a" * lead_byte_offset + "é".encode("utf-8") + b" more content follows"
        sample = body[:8192]
        self.assertEqual(len(sample), 8192)
        # Confirm the cut genuinely lands mid-character (i.e. this test
        # would have caught the pre-fix bug): a strict decode of just the
        # sample must fail, even though the full body is valid UTF-8.
        with self.assertRaises(UnicodeDecodeError):
            sample.decode("utf-8", errors="strict")
        body.decode("utf-8")  # the full body itself is unambiguously valid

        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
        )
        self.assertTrue(linter.content_sample_truncated)
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_genuinely_truncated_content_still_flagged(self):
        # A body that is short enough to fit entirely in content_sample,
        # and is fully received (complete=True), but genuinely ends
        # mid-character, should still be flagged: this isn't a sampling
        # artifact.
        body = "Café".encode("utf-8")[:-1]
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
            complete=True,
        )
        self.assertFalse(linter.content_sample_truncated)
        self.assertTrue(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_dropped_connection_not_flagged(self):
        # Regression: a short body cut off by a dropped connection
        # (complete=False) can also end mid-character without indicating
        # a real encoding problem -- and may be far shorter than the
        # 8192-byte cap, so this needs different handling than the
        # boundary case above.
        body = "Café".encode("utf-8")[:-1]
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
            complete=False,
        )
        self.assertFalse(linter.content_sample_truncated)
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_decode_failure_note_suppresses_false_undecodable(self):
        # Regression: content-encoding decoding that aborts partway
        # through (e.g. corrupt gzip) leaves content_sample as an
        # arbitrary prefix, which can also end mid-character. A
        # BAD_ZLIB/BAD_GZIP/BAD_BROTLI note already reports the real
        # problem; charset checks shouldn't pile a spurious one on top.
        body = "Café".encode("utf-8")[:-1]
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=utf-8")],
            body,
            extra_notes=[
                (
                    BAD_ZLIB,
                    {"zlib_error": "x", "ok_zlib_len": "0", "chunk_sample": "00"},
                )
            ],
        )
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_non_text_charset_name_does_not_crash(self):
        # Regression: codecs like "hex", "rot13", "base64" aren't text
        # encodings. bytes.decode() rejects them with LookupError, but
        # codecs.getincrementaldecoder() has no such guard and raises
        # codec-specific exceptions instead -- this must not reach that
        # path for a sample large enough to be truncated.
        body = ("Café naïve résumé привет " * 400).encode("utf-8")
        self.assertGreater(len(body), 8192)
        linter = _run(
            [(b"Content-Type", b"text/plain; charset=hex")],
            body,
        )
        self.assertTrue(_has_note(linter.notes, CHARSET_UNDECODABLE))


class DecodeDeclaredTest(unittest.TestCase):
    def test_short_truncated_sample_tolerated(self):
        # A sample far smaller than TRUNCATION_SAFETY_MARGIN (e.g. a
        # dropped connection after a handful of bytes) must still be
        # tolerated -- there's nothing left to trim.
        sample = "Café".encode("utf-8")[:-1]
        self.assertIsNotNone(_decode_declared(sample, "utf-8", truncated=True))

    def test_non_truncated_incomplete_sequence_rejected(self):
        sample = "Café".encode("utf-8")[:-1]
        self.assertIsNone(_decode_declared(sample, "utf-8", truncated=False))

    def test_non_text_codec_rejected_not_crashed(self):
        sample = ("Café naïve " * 400).encode("utf-8")
        self.assertIsNone(_decode_declared(sample, "hex", truncated=True))
        self.assertIsNone(_decode_declared(sample, "rot13", truncated=True))
        self.assertIsNone(_decode_declared(sample, "base64", truncated=True))

    def test_genuinely_corrupt_truncated_sample_still_rejected(self):
        # Tolerance only covers a trailing incomplete sequence; garbage
        # earlier in the sample must still fail.
        sample = b"\xff\xfe not valid utf-8 anywhere"
        self.assertIsNone(_decode_declared(sample, "utf-8", truncated=True))


class EncodingsCompatibleTest(unittest.TestCase):
    def test_asymmetric_truncated_tail_not_a_false_mismatch(self):
        # Regression: shift_jis (multi-byte) and cp1252 (single-byte)
        # disagree on how many characters a truncated tail represents --
        # shift_jis defers the incomplete lead byte, cp1252 decodes it
        # outright -- which must not manufacture a mismatch.
        sample = ("ABC" * 3000).encode("shift_jis") + "日".encode("shift_jis")[:1]
        self.assertTrue(
            _encodings_compatible("shift_jis", "cp1252", sample, truncated=True)
        )

    def test_real_mismatch_still_detected_when_truncated(self):
        # The tail trim must not mask a genuine mismatch elsewhere in a
        # truncated sample.
        sample = ("Привет мир! Москва " * 200).encode("windows-1251")
        self.assertGreater(len(sample), 8)
        self.assertFalse(
            _encodings_compatible("iso-8859-1", "windows-1251", sample, truncated=True)
        )

    def test_short_truncated_sample_treated_as_compatible(self):
        # Too little left after trimming to compare safely; err toward
        # not flagging a mismatch rather than risking a false one.
        sample = b"ab"
        self.assertTrue(
            _encodings_compatible("shift_jis", "cp1252", sample, truncated=True)
        )


class SampleIsTruncatedTest(unittest.TestCase):
    def test_untruncated_complete_sample(self):
        self.assertFalse(_sample_is_truncated(_FakeLinter()))

    def test_content_sample_truncated_flag(self):
        self.assertTrue(_sample_is_truncated(_FakeLinter(content_sample_truncated=True)))

    def test_incomplete_message(self):
        self.assertTrue(_sample_is_truncated(_FakeLinter(complete=False)))

    def test_decode_failure_note(self):
        note = BAD_ZLIB.__new__(BAD_ZLIB)
        self.assertTrue(_sample_is_truncated(_FakeLinter(notes=[note])))


if __name__ == "__main__":
    unittest.main()
