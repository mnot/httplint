import unittest

from httplint.field.codings import CODING_ALIAS_DEPRECATED
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import categories, levels


def response_notes(content_encoding):
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(b"Content-Encoding", content_encoding)])
    linter.finish_content(True)
    return [n for n in linter.notes if isinstance(n, CODING_ALIAS_DEPRECATED)]


def request_notes(*accept_encoding):
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
    linter.process_headers([(b"Accept-Encoding", value) for value in accept_encoding])
    linter.finish_content(True)
    return [n for n in linter.notes if isinstance(n, CODING_ALIAS_DEPRECATED)]


def rendered(note):
    return note.summary, " ".join(str(note.detail).split())


class TestCodingAlias(unittest.TestCase):
    def test_x_gzip_text(self):
        for notes in (
            response_notes(b"x-gzip"),
            response_notes(b"X-Gzip"),
            request_notes(b"x-gzip"),
            request_notes(b"gzip, x-gzip;q=0.5"),
        ):
            self.assertEqual(len(notes), 1)
            summary, detail = rendered(notes[0])
            self.assertEqual(summary, "The 'x-gzip' content-coding is a deprecated alias for 'gzip'.")
            self.assertIn(
                "lists <code>x-gzip</code> as deprecated, as an alias for <code>gzip</code>", detail
            )
            self.assertIn("IANA HTTP Content Coding Registry", detail)
            self.assertIn("rfc9110.html#section-8.4.1.3", detail)
            self.assertIn("SHOULD consider <code>x-gzip</code> to be equivalent to", detail)
            self.assertIn("senders should use <code>gzip</code>", detail)
            self.assertEqual(notes[0].level, levels.WARN)
            self.assertEqual(notes[0].category, categories.CONNEG)

    def test_x_compress_text(self):
        for notes in (response_notes(b"x-compress"), request_notes(b"X-Compress")):
            self.assertEqual(len(notes), 1)
            summary, detail = rendered(notes[0])
            self.assertEqual(
                summary, "The 'x-compress' content-coding is a deprecated alias for 'compress'."
            )
            self.assertIn(
                "lists <code>x-compress</code> as deprecated, as an alias for <code>compress</code>",
                detail,
            )
            self.assertIn("rfc9110.html#section-8.4.1.1", detail)
            self.assertIn("senders should use <code>compress</code>", detail)

    def test_one_note_per_field(self):
        self.assertEqual(len(response_notes(b"x-gzip, x-gzip")), 1)
        self.assertEqual(len(response_notes(b"x-gzip, gzip, X-GZIP")), 1)
        self.assertEqual(len(request_notes(b"x-gzip, x-gzip;q=0")), 1)
        self.assertEqual(len(request_notes(b"x-gzip", b"x-gzip")), 1)

    def test_each_alias_noted(self):
        notes = response_notes(b"x-gzip, x-compress")
        self.assertEqual(
            sorted(rendered(n)[0] for n in notes),
            [
                "The 'x-compress' content-coding is a deprecated alias for 'compress'.",
                "The 'x-gzip' content-coding is a deprecated alias for 'gzip'.",
            ],
        )

    def test_standard_names_have_no_note(self):
        self.assertEqual(response_notes(b"gzip, compress, br"), [])
        self.assertEqual(request_notes(b"gzip, compress;q=0.5, *"), [])


if __name__ == "__main__":
    unittest.main()
