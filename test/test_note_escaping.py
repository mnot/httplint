"""
Tests for the Note.summary / Note.detail contract.

Contract:
  summary -- plain text; vars are substituted but NOT HTML-escaped.
             Consumers must escape before embedding in HTML.
  detail  -- HTML-safe; Markdown renderer escapes user-controlled vars
             exactly once when they appear in code spans / indented blocks.
             Template authors must wrap vars in backtick spans.
"""

import unittest

from markupsafe import Markup

from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import Note, Notes, categories, levels


# ---------------------------------------------------------------------------
# Minimal Note subclasses used only in these tests
# ---------------------------------------------------------------------------

class NOTE_WITH_FIELD_NAME(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" is not a valid field name.'
    _text = 'The field `%(field_name)s` is invalid.'


class NOTE_WITH_PLAIN_VALUE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Unknown value '%(value)s'."
    _text = "The value `%(value)s` is not recognised."


class NOTE_WITH_PREESCAPED_CONTEXT(Note):
    """Simulates structured-field parse errors where context is raw text."""
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Parse error in %(field_name)s."
    _text = "Parse error:\n\n%(context)s"


# ---------------------------------------------------------------------------
# Unit tests: Note.summary is PLAIN TEXT (not HTML-escaped)
# ---------------------------------------------------------------------------

class NoteSummaryPlainTextTest(unittest.TestCase):
    """Note.summary must substitute vars but must NOT HTML-escape them."""

    def _make(self, note_cls, **vars):
        notes = Notes({"field_name": "X-Test"})
        return notes.add("test", note_cls, **vars)

    def test_summary_substitutes_vars(self):
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="hello world")
        self.assertIn("hello world", str(note.summary))

    def test_summary_does_not_escape_angle_brackets(self):
        """summary is plain text — <script> must pass through as-is."""
        note = self._make(NOTE_WITH_FIELD_NAME, field_name="<script>alert(1)</script>")
        summary = str(note.summary)
        self.assertIn("<script>", summary,
            msg="summary must NOT escape angle brackets — it is plain text")
        self.assertNotIn("&lt;", summary,
            msg="no HTML entities should appear in summary")

    def test_summary_does_not_escape_ampersand(self):
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="foo & bar")
        summary = str(note.summary)
        self.assertIn("foo & bar", summary)
        self.assertNotIn("&amp;", summary)

    def test_summary_result_is_str(self):
        """summary returns a plain str, not a Markup (which would suppress escaping)."""
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="safe")
        self.assertIsInstance(note.summary, str)
        self.assertNotIsInstance(note.summary, Markup)


# ---------------------------------------------------------------------------
# Unit tests: Note.detail is HTML-SAFE (Markdown handles escaping)
# ---------------------------------------------------------------------------

class NoteDetailHtmlSafeTest(unittest.TestCase):
    """Note.detail must produce HTML-safe output via the Markdown renderer.

    Values in backtick code spans or indented code blocks are escaped by
    Markdown exactly once.  The old approach of pre-escaping with escape()
    caused double-encoding (e.g. &amp;lt; instead of &lt;) inside code spans.
    """

    def _make(self, note_cls, **vars):
        notes = Notes({"field_name": "X-Test"})
        return notes.add("test", note_cls, **vars)

    def test_detail_escapes_angle_brackets_in_code_span(self):
        """Angle brackets in a code-span var appear as HTML entities."""
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="<b>bold</b>")
        self.assertNotIn("<b>", note.detail)
        self.assertIn("&lt;b&gt;", note.detail)

    def test_detail_does_not_double_escape_in_code_span(self):
        """Angle brackets must NOT be double-encoded (&amp;lt; instead of &lt;)."""
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="<b>bold</b>")
        self.assertNotIn("&amp;lt;", note.detail)

    def test_detail_escapes_ampersand_in_code_span(self):
        """Ampersands in a code-span var are encoded exactly once."""
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="a & b")
        detail = note.detail
        self.assertIn("&amp;", detail)
        self.assertNotIn("&amp;amp;", detail)

    def test_detail_escapes_html_in_indented_block(self):
        """HTML in a var that produces an indented code block is escaped."""
        raw_context = "\n\n    <script>alert(1)</script>\n    ^"
        note = self._make(NOTE_WITH_PREESCAPED_CONTEXT, context=raw_context)
        detail = note.detail
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)

    def test_detail_result_is_markup(self):
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="safe")
        self.assertIsInstance(note.detail, Markup)

    def test_detail_safe_value_unchanged_in_code_span(self):
        note = self._make(NOTE_WITH_PLAIN_VALUE, value="hello world")
        self.assertIn("hello world", note.detail)


# ---------------------------------------------------------------------------
# Integration tests: XSS via crafted HTTP headers
# ---------------------------------------------------------------------------

class IntegrationXSSTest(unittest.TestCase):
    """Crafted HTTP input must not produce unescaped HTML in note detail.

    summary is intentionally not checked here because it is plain text by
    contract; consumers are responsible for escaping summaries.
    """

    XSS_PAYLOAD = b"<script>alert(1)</script>"

    def _notes_for_bad_header_name(self, name: bytes) -> list:
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(name, b"value")])
        linter.finish_content(True)
        return list(linter.notes)

    def test_bad_header_name_detail_is_escaped(self):
        """A header name containing HTML must be escaped in the note detail."""
        notes = self._notes_for_bad_header_name(self.XSS_PAYLOAD)
        for note in notes:
            detail = str(note.detail)
            self.assertNotIn("<script>", detail,
                msg=f"Unescaped <script> in detail of {note.__class__.__name__}: {detail!r}")

    def test_bad_header_name_detail_no_double_encode(self):
        """detail must not double-encode entities for bad header names."""
        notes = self._notes_for_bad_header_name(self.XSS_PAYLOAD)
        for note in notes:
            detail = str(note.detail)
            self.assertNotIn("&amp;lt;", detail,
                msg=f"Double-encoded entity in detail of {note.__class__.__name__}: {detail!r}")

    def _notes_for_structured_field_parse_error(self, value: bytes) -> list:
        """Send a structured-field header that will fail to parse."""
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Accept-CH", value)])
        linter.finish_content(True)
        return list(linter.notes)

    def test_structured_field_parse_error_detail_is_escaped(self):
        """A structured-field parse error must not leak raw HTML into the detail."""
        payload = b"<img src=x onerror=alert(1)>"
        notes = self._notes_for_structured_field_parse_error(payload)
        for note in notes:
            detail = str(note.detail)
            self.assertNotIn("<img", detail,
                msg=f"Unescaped HTML in detail of {note.__class__.__name__}: {detail!r}")


if __name__ == "__main__":
    unittest.main()
