"""
Declared charsets resolve through the Encoding Standard's labels, not Python's codec
registry; content is decoded the way recipients decode it.
"""

import unittest

from httplint.charset import (
    _CHARDET_ALIASES,
    _canonical,
    CHARSET_MISMATCH,
    CHARSET_UNDECODABLE,
    can_decode,
    decode_bytes,
    whatwg_encoding,
)
from httplint.charset_data import SINGLE_BYTE, WHATWG_LABELS
from httplint.message import HttpResponseLinter


def _run(content_type, body):
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(
        [(b"Content-Type", content_type), (b"Content-Length", str(len(body)).encode())]
    )
    linter.feed_content(body)
    linter.finish_content(True)
    return linter


def _has_note(linter, cls):
    return any(isinstance(n, cls) for n in linter.notes)


class WhatwgEncodingTest(unittest.TestCase):
    def test_labels(self):
        for label, encoding in [
            ("utf-8", "UTF-8"),
            ("UTF8", "UTF-8"),
            (" Utf-8\t", "UTF-8"),
            ("latin1", "windows-1252"),
            ("iso-8859-1", "windows-1252"),
            ("us-ascii", "windows-1252"),
            ("gb2312", "GBK"),
            ("ks_c_5601-1987", "EUC-KR"),
            ("utf-16", "UTF-16LE"),
            ("iso-2022-kr", "replacement"),
            ("x-user-defined", "x-user-defined"),
        ]:
            with self.subTest(label=label):
                self.assertEqual(whatwg_encoding(label), encoding)

    def test_not_labels(self):
        # Registered with Python, but nothing recipients use as a charset.
        for label in ("unicode_escape", "idna", "punycode", "charmap", "hex", "utf-32", "mac-roman"):
            with self.subTest(label=label):
                self.assertIsNone(whatwg_encoding(label))
        self.assertIsNone(whatwg_encoding(""))
        self.assertIsNone(whatwg_encoding(None))

    def test_ascii_case_folding_only(self):
        # U+212A (Kelvin sign) lowercases to "k"; the Standard folds ASCII only.
        self.assertIsNone(whatwg_encoding("Koi8-r"))
        self.assertEqual(whatwg_encoding("KOI8-R"), "KOI8-R")

    def test_every_encoding_can_be_checked(self):
        for label, encoding in WHATWG_LABELS.items():
            with self.subTest(label=label):
                self.assertEqual(can_decode(encoding), encoding != "replacement")


class DecodeBytesTest(unittest.TestCase):
    def test_windows_1252_maps_every_byte(self):
        # Python's cp1252 rejects these five; recipients show C1 controls.
        self.assertEqual(decode_bytes(b"\x81\x8d\x8f\x90\x9d", "windows-1252"), "\x81\x8d\x8f\x90\x9d")
        self.assertIsNotNone(decode_bytes(bytes(range(256)), "windows-1252"))

    def test_unmapped_byte_is_an_error(self):
        self.assertIsNone(decode_bytes(b"\xaa", "windows-1253"))

    def test_single_byte_tables_agree_with_python(self):
        for encoding, codec in [
            ("ISO-8859-2", "iso8859-2"),
            ("ISO-8859-15", "iso8859-15"),
            ("KOI8-R", "koi8-r"),
            ("macintosh", "mac-roman"),
            ("IBM866", "cp866"),
        ]:
            with self.subTest(encoding=encoding):
                data = bytes(range(0x80, 0x100))
                self.assertEqual(decode_bytes(data, encoding), data.decode(codec))

    def test_where_the_standard_differs_from_python(self):
        # KOI8-U puts Belarusian letters where Python's codec has box-drawing characters.
        self.assertEqual(decode_bytes(b"\xae\xbe", "KOI8-U"), "ўЎ")
        self.assertEqual(b"\xae\xbe".decode("koi8-u"), "╝╬")

    def test_iso_8859_8_i_is_iso_8859_8(self):
        self.assertEqual(SINGLE_BYTE["ISO-8859-8-I"], SINGLE_BYTE["ISO-8859-8"])

    def test_x_user_defined(self):
        self.assertEqual(decode_bytes(b"a\x80\xff", "x-user-defined"), "a")

    def test_multi_byte(self):
        self.assertEqual(decode_bytes("日本語".encode("shift_jis"), "Shift_JIS"), "日本語")
        self.assertEqual(decode_bytes("日本語".encode("euc_jp"), "EUC-JP"), "日本語")
        self.assertEqual(decode_bytes("한국어".encode("euc_kr"), "EUC-KR"), "한국어")
        # GBK is gb18030's decoder in the Standard; 龘 isn't in gb2312.
        self.assertEqual(decode_bytes("龘".encode("gbk"), "GBK"), "龘")
        self.assertIsNone(decode_bytes(b"\xc3\x28", "UTF-8"))

    def test_gbk_lone_0x80_is_the_euro_sign(self):
        # The Standard's gb18030 decoder maps it; Python's rejects it.
        for data, text in [
            (b"\x80", "\u20ac"),
            (b"\x00\x80", "\x00\u20ac"),
            (b"\x80A", "\u20acA"),
            (b"a\x80\xb0\xa1", "a\u20ac" + b"\xb0\xa1".decode("gbk")),
        ]:
            with self.subTest(data=data):
                self.assertEqual(decode_bytes(data, "GBK"), text)
                self.assertEqual(decode_bytes(data, "gb18030"), text)
        # As the trail byte of a two-byte sequence it's an ordinary 0x80.
        self.assertEqual(decode_bytes(b"\x81\x80", "GBK"), b"\x81\x80".decode("gb18030"))
        # Other errors are still errors.
        self.assertIsNone(decode_bytes(b"\x81\x20", "GBK"))
        self.assertIsNone(decode_bytes(b"\xff", "GBK"))

    def test_byte_order_mark_outranks_the_label(self):
        text = "h\u00e9llo"
        for label in ("UTF-8", "UTF-16LE", "UTF-16BE", "windows-1252", "Shift_JIS"):
            with self.subTest(label=label):
                self.assertEqual(decode_bytes(b"\xfe\xff" + text.encode("utf-16-be"), label), text)
                self.assertEqual(decode_bytes(b"\xff\xfe" + text.encode("utf-16-le"), label), text)
                self.assertEqual(decode_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"), label), text)

    def test_byte_order_mark_can_be_ignored(self):
        data = b"\xff\xfeh\x00i\x00"
        self.assertIsNone(decode_bytes(data, "UTF-8", sniff_bom=False))
        self.assertEqual(decode_bytes(data, "UTF-8"), "hi")

    def test_truncated_sample_with_byte_order_mark(self):
        data = b"\xff\xfe" + "hi\U0001f600".encode("utf-16-le")[:-1]
        self.assertIsNone(decode_bytes(data, "UTF-8", truncated=False))
        self.assertEqual(decode_bytes(data, "UTF-8", truncated=True), "hi")

    def test_euc_jp_falls_back_to_jisx0213(self):
        with self.assertRaises(UnicodeDecodeError):
            b"\xa2\xaf".decode("euc_jp")
        self.assertIsNotNone(decode_bytes(b"\xa2\xaf", "EUC-JP"))
        self.assertEqual(decode_bytes(b"\xad\xa1", "EUC-JP"), "\u2460")  # NEC row 13

    def test_replacement_and_unknown_have_no_decoder(self):
        self.assertIsNone(decode_bytes(b"abc", "replacement"))
        self.assertIsNone(decode_bytes(b"abc", "nonesuch"))


class DetectedNameTest(unittest.TestCase):
    def test_chardet_names_resolve_to_the_standards_names(self):
        for detected, encoding in [
            ("UTF-8-SIG", "UTF-8"),
            ("CP932", "Shift_JIS"),
            ("CP949", "EUC-KR"),
            ("GB2312", "GBK"),
            ("ISO-8859-1", "windows-1252"),
            ("Windows-1252", "windows-1252"),
            ("MacRoman", "macintosh"),
            ("TIS-620", "windows-874"),
            ("ISO-8859-16", "ISO-8859-16"),
            ("UTF-16", "UTF-16LE"),
        ]:
            with self.subTest(detected=detected):
                self.assertEqual(_canonical(detected), encoding)

    def test_aliases_all_resolve(self):
        for alias, label in _CHARDET_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIsNotNone(whatwg_encoding(label))

    def test_others_fall_back_to_python_if_it_has_a_text_codec(self):
        self.assertEqual(_canonical("Johab"), "py:johab")
        self.assertIsNone(_canonical("EUC-TW"))
        self.assertIsNone(_canonical("hex"))


class VerifyAgainstLabelsTest(unittest.TestCase):
    def test_windows_1252_with_undefined_bytes_is_decodable(self):
        body = b"caf\xe9 \x81 \x8d \x90 texte pour que chardet ait de quoi faire " * 5
        linter = _run(b"text/html; charset=windows-1252", body)
        self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))

    def test_gb2312_label_decodes_as_gbk(self):
        body = "中文网页内容测试。龘龙 ".encode("gbk") * 10
        linter = _run(b"text/html; charset=gb2312", body)
        self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))
        self.assertFalse(_has_note(linter, CHARSET_MISMATCH))

    def test_gbk_with_euro_sign_byte_is_decodable(self):
        body = ("中文网页内容测试。" * 20).encode("gbk") + b" \x80" * 5
        linter = _run(b"text/html; charset=gbk", body)
        self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))

    def test_utf_16_content_under_an_8_bit_label_is_a_mismatch_not_undecodable(self):
        # Browsers follow the byte order mark and cope; the label is still wrong.
        body = b"\xff\xfe" + ("h\u00e9llo w\u00f6rld, some text to detect. " * 20).encode("utf-16-le")
        linter = _run(b"text/plain; charset=utf-8", body)
        self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))
        self.assertTrue(_has_note(linter, CHARSET_MISMATCH))

    def test_truncated_shift_jis_is_not_a_mismatch(self):
        # chardet calls this CP932; the sample cap can cut a character in half.
        body = ("a" + "日本語のテキストです。" * 2000).encode("cp932")
        linter = _run(b"text/html; charset=shift_jis", body)
        self.assertFalse(_has_note(linter, CHARSET_MISMATCH))
        self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))

    def test_windows_874_label_is_checked(self):
        # Python spells it cp874, so it used to be skipped as unknown.
        body = "สวัสดีครับ ยินดีต้อนรับ ".encode("cp874") * 20
        self.assertFalse(_has_note(_run(b"text/html; charset=windows-874", body), CHARSET_UNDECODABLE))
        body = "caf\xe9 déjà vu ".encode("latin-1") * 20 + b"\xdb"  # 0xDB is unmapped
        self.assertTrue(_has_note(_run(b"text/html; charset=windows-874", body), CHARSET_UNDECODABLE))

    def test_python_only_codecs_are_not_checked(self):
        body = "Café naïve résumé ".encode("utf-8") * 20
        for charset in (b"unicode_escape", b"idna", b"punycode", b"charmap", b"utf-7", b"nonesuch"):
            with self.subTest(charset=charset):
                linter = _run(b"text/html; charset=" + charset, body)
                self.assertIsNone(linter.character_encoding)
                self.assertIsNone(linter.whatwg_encoding)
                self.assertFalse(_has_note(linter, CHARSET_UNDECODABLE))
                self.assertFalse(_has_note(linter, CHARSET_MISMATCH))

    def test_character_encoding_stays_the_declared_string(self):
        for charset, declared in [(b"UTF8", "UTF8"), (b"latin1", "latin1"), (b"gb2312", "gb2312")]:
            with self.subTest(charset=charset):
                linter = _run(b"text/plain; charset=" + charset, b"x")
                self.assertEqual(linter.character_encoding, declared)

    def test_whatwg_encoding_is_the_resolved_name(self):
        for charset, encoding in [
            (b"UTF8", "UTF-8"),
            (b"latin1", "windows-1252"),
            (b"gb2312", "GBK"),
            (b"windows-874", "windows-874"),
        ]:
            with self.subTest(charset=charset):
                linter = _run(b"text/plain; charset=" + charset, b"x")
                self.assertEqual(linter.whatwg_encoding, encoding)

    def test_python_cant_decode_it(self):
        # Known to recipients, but not a Python codec; consumers decode with Python.
        linter = _run(b"text/plain; charset=windows-874", b"x")
        self.assertEqual(linter.whatwg_encoding, "windows-874")
        self.assertIsNone(linter.character_encoding)

    def test_replacement_labels_are_not_recorded(self):
        linter = _run(b"text/plain; charset=iso-2022-kr", b"x")
        self.assertEqual(linter.whatwg_encoding, "replacement")
        self.assertIsNone(linter.character_encoding)

    def test_no_charset(self):
        linter = _run(b"text/plain", b"x")
        self.assertIsNone(linter.whatwg_encoding)
        self.assertIsNone(linter.character_encoding)


if __name__ == "__main__":
    unittest.main()
