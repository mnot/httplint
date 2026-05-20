import unittest

from httplint.charset import (
    CHARSET_IMPLICIT_MISMATCH,
    CHARSET_MISMATCH,
    CHARSET_UNDECODABLE,
)
from httplint.message import HttpResponseLinter


def _run(headers, body):
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(headers + [(b"Content-Length", str(len(body)).encode())])
    linter.feed_content(body)
    linter.finish_content(True)
    return linter


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


if __name__ == "__main__":
    unittest.main()
