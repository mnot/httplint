import unittest

from httplint.charset import (
    CHARSET_IMPLICIT_MISMATCH,
    CHARSET_LABEL_REMAPPED,
    CHARSET_MISMATCH,
    CHARSET_UNDECODABLE,
    REMAPPED_LABELS,
    _canonical,
    _encodings_compatible,
    _sample_is_truncated,
    decode_bytes,
    format_byte_ranges,
    is_text_encoding,
    remapped_bytes,
)
from httplint.charset_data import WHATWG_LABELS
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
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_non_text_charset_not_recorded(self):
        for name in (b"hex", b"base64", b"zlib", b"rot13", b"bz2"):
            with self.subTest(name=name):
                linter = _run([(b"Content-Type", b"text/plain; charset=" + name)], b"x")
                self.assertIsNone(linter.character_encoding)

    def test_undefined_charset_does_not_crash(self):
        body = ("Café naïve résumé " * 10).encode("utf-8")
        linter = _run([(b"Content-Type", b"text/plain; charset=undefined")], body)
        self.assertIsNone(linter.character_encoding)
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE))

    def test_text_charset_recorded(self):
        linter = _run([(b"Content-Type", b"text/plain; charset=UTF8")], b"x")
        self.assertEqual(linter.character_encoding, "UTF8")


class LabelRemappedTest(unittest.TestCase):
    """
    Labels for registered charsets that browsers decode as a Windows one: content those
    charsets can't carry shows something in a browser, but not for everyone.
    """

    TEXT = "Il a dit \u201cbonjour\u201d \u2014 caf\u00e9 \u20ac5 et encore du texte. " * 4
    THAI = "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e04\u0e23\u0e31\u0e1a " * 20
    TURKISH = (
        "\u011fe\u00e7\u0131\u015f \u201cm\u00fc\u015fteri\u201d \u20ac5 yaz\u0131 \u0130\u00d6 "
        * 8
    )

    def remapped(self, label, body):
        linter = _run([(b"Content-Type", b"text/html; charset=" + label)], body)
        self.assertFalse(_has_note(linter.notes, CHARSET_UNDECODABLE), label)
        return _has_note(linter.notes, CHARSET_LABEL_REMAPPED)

    def test_latin1_labels_on_windows_1252_content(self):
        for label in (b"iso-8859-1", b"latin1", b"ISO_8859-1", b"l1"):
            with self.subTest(label=label):
                self.assertTrue(self.remapped(label, self.TEXT.encode("cp1252")))

    def test_ascii_labels_on_windows_1252_content(self):
        for label in (b"us-ascii", b"ascii", b"US-ASCII"):
            with self.subTest(label=label):
                self.assertTrue(self.remapped(label, self.TEXT.encode("cp1252")))

    def test_latin5_labels_on_windows_1254_content(self):
        for label in (b"iso-8859-9", b"latin5", b"l5"):
            with self.subTest(label=label):
                self.assertTrue(self.remapped(label, self.TURKISH.encode("cp1254")))

    def test_thai_labels_on_windows_874_content(self):
        body = (self.THAI + "\u2026 \u201csawasdee\u201d").encode("cp874")
        for label in (b"tis-620", b"iso-8859-11", b"ISO8859-11"):
            with self.subTest(label=label):
                self.assertTrue(self.remapped(label, body))

    def test_thai_no_break_space_is_not_worth_a_note(self):
        # Pages labelled tis-620 use 0xA0 as a no-break space, though TIS-620 leaves it
        # undefined.
        body = (self.THAI + "\u00a0" + self.THAI).encode("iso8859-11")
        self.assertFalse(self.remapped(b"tis-620", body))

    def test_content_the_registered_charset_can_carry_is_fine(self):
        for label, text, codec in [
            (b"iso-8859-1", "Caf\u00e9 r\u00e9sum\u00e9 na\u00efve gar\u00e7on " * 40, "latin-1"),
            (
                b"iso-8859-9",
                "\u011fe\u00e7\u0131\u015f \u00fc\u015fteri yaz\u0131 \u0130\u00d6 " * 20,
                "iso8859-9",
            ),
            (b"tis-620", self.THAI, "tis-620"),
            (b"iso-8859-11", self.THAI + "\u00a0", "iso8859-11"),
        ]:
            with self.subTest(label=label):
                self.assertFalse(self.remapped(label, text.encode(codec)))

    def test_only_bytes_that_differ_count(self):
        # 0x81 is U+0081 in both ISO-8859-1 and windows-1252; 0x93 is not.
        body = b"caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9 caf\xe9"
        self.assertFalse(self.remapped(b"iso-8859-1", body + b" \x81"))
        self.assertTrue(self.remapped(b"iso-8859-1", body + b" \x93"))

    def test_windows_labels_are_not_remapped(self):
        for label, codec in [
            (b"windows-1252", "cp1252"),
            (b"windows-1254", "cp1254"),
            (b"windows-874", "cp874"),
        ]:
            with self.subTest(label=label):
                body = (self.TEXT if codec == "cp1252" else self.THAI + "\u2026").encode(
                    codec, "replace"
                )
                self.assertFalse(self.remapped(label, body))

    def test_ascii_content_is_fine(self):
        self.assertFalse(self.remapped(b"us-ascii", b"plain text " * 20))

    def test_utf8_content_gets_the_mismatch_note_instead(self):
        # The label is wrong whatever browsers do; one note says so.
        linter = _run(
            [(b"Content-Type", b"text/html; charset=us-ascii")], self.TEXT.encode("utf-8")
        )
        self.assertTrue(_has_note(linter.notes, CHARSET_MISMATCH))
        self.assertFalse(_has_note(linter.notes, CHARSET_LABEL_REMAPPED))

    def test_note_names_the_encoding_and_the_bytes(self):
        linter = _run(
            [(b"Content-Type", b"text/html; charset=tis-620")],
            (self.THAI + "\u201chi\u201d").encode("cp874"),
        )
        note = next(n for n in linter.notes if isinstance(n, CHARSET_LABEL_REMAPPED))
        self.assertIn("<code>windows-874</code>", str(note.detail))
        # The bytes in the content, not every byte that differs.
        self.assertIn("(0x93-0x94)", str(note.detail))


class RemappedLabelsTest(unittest.TestCase):
    def test_covers_every_label_the_standard_remaps(self):
        # Labels for a registered charset that the Standard maps to a Windows encoding;
        # the Windows encodings' own labels aren't remapped.
        native = {
            "windows-1252": {"cp1252", "windows-1252", "x-cp1252"},
            "windows-1254": {"cp1254", "windows-1254", "x-cp1254"},
            "windows-874": {"dos-874", "windows-874"},
        }
        for encoding, own in native.items():
            expected = {l for l, e in WHATWG_LABELS.items() if e == encoding} - own
            covered = {l for l in REMAPPED_LABELS if WHATWG_LABELS.get(l) == encoding}
            self.assertEqual(covered, expected, encoding)
        self.assertEqual({WHATWG_LABELS[l] for l in REMAPPED_LABELS}, set(native))

    def test_codecs_exist(self):
        for label, codec in REMAPPED_LABELS.items():
            with self.subTest(label=label):
                self.assertTrue(is_text_encoding(codec))

    def test_remapped_bytes_per_label(self):
        # Pinned, so a wrong codec for one label shows up. Windows-1252 and its Latin-1
        # spellings differ only where windows-1252 has printable characters; windows-1254
        # likewise; Thai differs in the C1 range where windows-874 has punctuation.
        latin1 = frozenset({0x80, *range(0x82, 0x8D), 0x8E, *range(0x91, 0x9D), 0x9E, 0x9F})
        latin5 = frozenset({0x80, *range(0x82, 0x8D), *range(0x91, 0x9D), 0x9F})
        thai = frozenset({0x80, 0x85, *range(0x91, 0x98)})
        expected = {
            frozenset(range(0x80, 0x100)): ["us-ascii", "ascii", "ansi_x3.4-1968"],
            latin1: ["iso-8859-1", "latin1", "l1", "csisolatin1", "ibm819", "iso-ir-100"],
            latin5: ["iso-8859-9", "latin5", "l5", "csisolatin5", "iso-ir-148", "iso88599"],
            thai: ["tis-620", "iso-8859-11", "iso8859-11", "iso885911"],
        }
        for differing, labels in expected.items():
            for label in labels:
                with self.subTest(label=label):
                    self.assertEqual(remapped_bytes(label), differing)

    def test_remapped_bytes_normalises_the_label(self):
        self.assertEqual(remapped_bytes("US-ASCII"), remapped_bytes("us-ascii"))
        self.assertEqual(remapped_bytes(" Latin1\t"), remapped_bytes("latin1"))
        self.assertNotEqual(remapped_bytes("TIS-620"), frozenset())

    def test_remapped_bytes(self):
        self.assertEqual(remapped_bytes("us-ascii"), frozenset(range(0x80, 0x100)))
        self.assertEqual(remapped_bytes("windows-1252"), frozenset())
        self.assertEqual(remapped_bytes("nonesuch"), frozenset())
        # windows-1252 differs from ISO-8859-1 only where it has printable characters.
        latin1 = remapped_bytes("latin1")
        self.assertTrue(latin1 <= set(range(0x80, 0xA0)))
        self.assertIn(0x93, latin1)
        self.assertNotIn(0x81, latin1)

    def test_format_byte_ranges(self):
        self.assertEqual(format_byte_ranges(frozenset()), "")
        self.assertEqual(format_byte_ranges(frozenset({0x80})), "0x80")
        self.assertEqual(
            format_byte_ranges(frozenset({0x80, 0x82, 0x83, 0x84, 0x91})), "0x80, 0x82-0x84, 0x91"
        )


class IsTextEncodingTest(unittest.TestCase):
    def test_non_text_codecs_rejected(self):
        for name in ("hex", "base64", "zlib", "rot13", "bz2", "uu", "undefined"):
            with self.subTest(name=name):
                self.assertFalse(is_text_encoding(name))
                self.assertIsNone(_canonical(name))

    def test_unknown_and_malformed_rejected(self):
        for name in ("nonesuch", "", "utf\x008", None):
            with self.subTest(name=name):
                self.assertFalse(is_text_encoding(name))

    def test_text_encodings_accepted(self):
        for name in (
            "utf-8",
            "UTF8",
            "iso-8859-1",
            "windows-1252",
            "shift_jis",
            "utf-16",
            "utf-16le",
            "utf-32",
            "utf-32be",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_text_encoding(name))
                self.assertIsNotNone(_canonical(name))


class DecodeBytesTest(unittest.TestCase):
    def test_short_truncated_sample_tolerated(self):
        # A sample far smaller than TRUNCATION_SAFETY_MARGIN (e.g. a
        # dropped connection after a handful of bytes) must still be
        # tolerated -- there's nothing left to trim.
        sample = "Café".encode("utf-8")[:-1]
        self.assertIsNotNone(decode_bytes(sample, "UTF-8", truncated=True))

    def test_non_truncated_incomplete_sequence_rejected(self):
        sample = "Café".encode("utf-8")[:-1]
        self.assertIsNone(decode_bytes(sample, "UTF-8", truncated=False))

    def test_non_text_codec_rejected_not_crashed(self):
        sample = ("Café naïve " * 400).encode("utf-8")
        self.assertIsNone(decode_bytes(sample, "py:hex", truncated=True))
        self.assertIsNone(decode_bytes(sample, "py:rot13", truncated=True))
        self.assertIsNone(decode_bytes(sample, "py:base64", truncated=True))

    def test_bare_unicode_error_codec_rejected(self):
        # "undefined" raises a plain UnicodeError, not UnicodeDecodeError.
        self.assertIsNone(decode_bytes(b"caf\xc3\xa9", "py:undefined", truncated=False))
        self.assertIsNone(decode_bytes(b"caf\xc3\xa9", "py:undefined", truncated=True))

    def test_genuinely_corrupt_truncated_sample_still_rejected(self):
        # Tolerance only covers a trailing incomplete sequence; garbage
        # earlier in the sample must still fail.
        sample = b"\xc0\xaf not valid utf-8 anywhere"
        self.assertIsNone(decode_bytes(sample, "UTF-8", truncated=True))


class EncodingsCompatibleTest(unittest.TestCase):
    def test_asymmetric_truncated_tail_not_a_false_mismatch(self):
        # Regression: shift_jis (multi-byte) and cp1252 (single-byte)
        # disagree on how many characters a truncated tail represents --
        # shift_jis defers the incomplete lead byte, cp1252 decodes it
        # outright -- which must not manufacture a mismatch.
        sample = ("ABC" * 3000).encode("shift_jis") + "日".encode("shift_jis")[:1]
        self.assertTrue(_encodings_compatible("Shift_JIS", "windows-1252", sample, truncated=True))

    def test_real_mismatch_still_detected_when_truncated(self):
        # The tail trim must not mask a genuine mismatch elsewhere in a
        # truncated sample.
        sample = ("Привет мир! Москва " * 200).encode("windows-1251")
        self.assertGreater(len(sample), 8)
        self.assertFalse(
            _encodings_compatible("windows-1252", "windows-1251", sample, truncated=True)
        )

    def test_short_truncated_sample_treated_as_compatible(self):
        # Too little left after trimming to compare safely; err toward
        # not flagging a mismatch rather than risking a false one.
        sample = b"ab"
        self.assertTrue(_encodings_compatible("Shift_JIS", "windows-1252", sample, truncated=True))


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
