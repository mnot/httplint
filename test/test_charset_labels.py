"""
Declared charsets resolve through the Encoding Standard's labels, not Python's codec
registry; content is decoded the way recipients decode it.
"""

import unittest

from httplint.charset import (
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

    def test_utf_16_byte_order_mark_outranks_the_label(self):
        text = "héllo"
        self.assertEqual(decode_bytes(b"\xfe\xff" + text.encode("utf-16-be"), "UTF-16LE"), "﻿" + text)
        self.assertEqual(decode_bytes(b"\xff\xfe" + text.encode("utf-16-le"), "UTF-16BE"), "﻿" + text)

    def test_replacement_and_unknown_have_no_decoder(self):
        self.assertIsNone(decode_bytes(b"abc", "replacement"))
        self.assertIsNone(decode_bytes(b"abc", "nonesuch"))


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
