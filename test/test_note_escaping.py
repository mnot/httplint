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
from unittest import mock

from markupsafe import Markup

from httplint.field.parsers.accept_query import ACCEPT_QUERY_BAD_SYNTAX
from httplint.field.utils import MEDIA_TYPE_BAD_NAME
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


class NOTE_WITH_TWO_VALUES(Note):
    """Two independent wire-supplied vars, for placeholder-collision tests."""
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Two values: '%(a)s' and '%(b)s'."
    _text = "%(a)s | %(b)s"


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


# ---------------------------------------------------------------------------
# Regression tests for #158: wire-supplied values render literally
# (HTML-escaped) in Note.detail, instead of having backticks stripped.
# ---------------------------------------------------------------------------

def _response_notes(headers: list) -> list:
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(headers)
    linter.finish_content(True)
    return list(linter.notes)


class WireValueMarkdownInjectionTest(unittest.TestCase):
    """A wire value is never parsed as Markdown, so it can't lose or smuggle
    characters -- it just shows up literally, HTML-escaped."""

    def test_media_type_bad_name_preserves_backtick(self):
        """A backtick in the offending media type must be visible, not stripped."""
        notes = _response_notes([(b"Content-Type", b"te`xt/plain")])
        bad_name_notes = [n for n in notes if isinstance(n, MEDIA_TYPE_BAD_NAME)]
        self.assertTrue(bad_name_notes, "MEDIA_TYPE_BAD_NAME was not raised")
        detail = str(bad_name_notes[0].detail)
        self.assertIn("te`xt/plain", detail)

    def test_accept_query_bad_syntax_escapes_backtick_html_payload(self):
        """A media range combining a backtick with raw HTML renders fully escaped."""
        payload = b'"text/`</code>-<img src=x onerror=alert(1)>"'
        notes = _response_notes([(b"Accept-Query", payload)])
        bad_syntax_notes = [n for n in notes if isinstance(n, ACCEPT_QUERY_BAD_SYNTAX)]
        self.assertTrue(bad_syntax_notes, "ACCEPT_QUERY_BAD_SYNTAX was not raised")
        detail = str(bad_syntax_notes[0].detail)
        self.assertIn("text/`", detail)
        self.assertNotIn("<img", detail)
        self.assertIn("&lt;img", detail)

    def test_accept_query_bad_syntax_escapes_script_payload(self):
        """A media range containing a script tag renders fully escaped."""
        payload = b'"text/pl in<script>alert(1)</script>"'
        notes = _response_notes([(b"Accept-Query", payload)])
        bad_syntax_notes = [n for n in notes if isinstance(n, ACCEPT_QUERY_BAD_SYNTAX)]
        self.assertTrue(bad_syntax_notes, "ACCEPT_QUERY_BAD_SYNTAX was not raised")
        detail = str(bad_syntax_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)


class PlaceholderSubstitutionTest(unittest.TestCase):
    """A wire value that mimics a placeholder token must not confuse the
    post-render substitution in Note._get_detail."""

    def _make(self, **vars):
        notes = Notes({"field_name": "X-Test"})
        return notes.add("test", NOTE_WITH_TWO_VALUES, **vars)

    def test_value_containing_another_vars_placeholder_is_not_resubstituted(self):
        fixed_nonce = "deadbeef" * 4
        a_placeholder = f"{fixed_nonce}:a"
        with mock.patch("httplint.note.secrets.token_hex", return_value=fixed_nonce):
            note = self._make(a="innocuous", b=f"before {a_placeholder} after")
            detail = str(note.detail)
        self.assertIn("innocuous", detail)
        self.assertIn(f"before {a_placeholder} after", detail)
        self.assertNotIn("before innocuous after", detail)


if __name__ == "__main__":
    unittest.main()
