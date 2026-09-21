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

from httplint.field import BAD_SYNTAX_DETAILED
from httplint.field.parsers.accept_ch import ACCEPT_CH_MISSING_VARY
from httplint.field.parsers.accept_query import ACCEPT_QUERY_BAD_SYNTAX
from httplint.field.parsers.cache_status import CACHE_STATUS
from httplint.field.parsers.clear_site_data import CSD_PRESENT
from httplint.field.structured_field import STRUCTURED_FIELD_PARSE_ERROR
from httplint.field.utils import MEDIA_TYPE_BAD_NAME
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import MarkdownSafe, Note, Notes, categories, levels


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


def _request_notes(headers: list) -> list:
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
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


class BareProseVarTest(unittest.TestCase):
    """The core invariant behind dropping KNOWN_SAFE_VARS: a var need not be
    wrapped in a code span for Note.detail to escape it. Before this fix,
    Note._get_detail() only escaped values that landed in a Markdown code
    span or indented block; a var interpolated into bare prose had its raw
    HTML passed straight through, because Markdown treats inline `<...>`
    as literal passthrough HTML by default."""

    class NOTE_WITH_BARE_VALUE(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "Bare value '%(value)s'."
        _text = "The value %(value)s is not recognised."  # deliberately unwrapped

    def test_bare_prose_value_is_escaped(self):
        notes = Notes({"field_name": "X-Test"})
        note = notes.add("test", self.NOTE_WITH_BARE_VALUE, value="<script>alert(1)</script>")
        detail = str(note.detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)


class FormerlyMisclassifiedVarsTest(unittest.TestCase):
    """Regression tests for vars that KNOWN_SAFE_VARS wrongly exempted from
    escaping (method, missing_fields) or wrongly let lose their intended
    Markdown structure (context, in both STRUCTURED_FIELD_PARSE_ERROR and
    BAD_SYNTAX_DETAILED). Dropping KNOWN_SAFE_VARS in favor of MarkdownSafe
    fixes both classes of bug."""

    def test_accept_ch_missing_vary_escapes_injected_field_name(self):
        """Accept-CH lets an SF String bypass its Token type check, reaching
        `missing_fields` (formerly wrongly marked SF-Token-constrained)."""
        payload = b'"evil</script><script>alert(1)</script>", Sec-CH-UA'
        notes = _response_notes([(b"Accept-CH", payload), (b"Vary", b"Accept")])
        missing_vary_notes = [n for n in notes if isinstance(n, ACCEPT_CH_MISSING_VARY)]
        self.assertTrue(missing_vary_notes, "ACCEPT_CH_MISSING_VARY was not raised")
        detail = str(missing_vary_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)

    def test_cache_status_escapes_injected_target_name(self):
        """The Cache-Status cache name (formerly hand-spliced, unescaped, into
        a bare **bold** marker) must render escaped."""
        payload = b'"Evil</script><script>alert(1)</script>"; hit'
        notes = _response_notes([(b"Cache-Status", payload)])
        cache_status_notes = [n for n in notes if isinstance(n, CACHE_STATUS)]
        self.assertTrue(cache_status_notes, "CACHE_STATUS was not raised")
        detail = str(cache_status_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)

    def test_cache_status_param_value_backtick_does_not_break_span(self):
        """A cache-key param value containing a backtick must not close the
        hand-built code span check_sf_params() wraps it in."""
        payload = b'ExampleCache; key="a`b<script>alert(1)</script>"'
        notes = _response_notes([(b"Cache-Status", payload)])
        cache_status_notes = [n for n in notes if isinstance(n, CACHE_STATUS)]
        self.assertTrue(cache_status_notes, "CACHE_STATUS was not raised")
        detail = str(cache_status_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)

    def test_structured_field_parse_error_context_preserves_backtick(self):
        """The wire excerpt around a Structured Field parse error must show
        an embedded backtick literally, and still escape HTML."""
        notes = _response_notes([(b"Accept-CH", b'"unterm`inated<script>x')])
        parse_error_notes = [n for n in notes if isinstance(n, STRUCTURED_FIELD_PARSE_ERROR)]
        self.assertTrue(parse_error_notes, "STRUCTURED_FIELD_PARSE_ERROR was not raised")
        detail = str(parse_error_notes[0].detail)
        self.assertIn("`", detail)
        self.assertNotIn("<script>", detail)

    def test_bad_syntax_detailed_context_preserves_backtick(self):
        """The wire excerpt around a list-field syntax error must show an
        embedded backtick literally, and still escape HTML."""
        notes = _request_notes([(b"Trailer", b"abc`def@ghi<script>alert(1)</script>")])
        detailed_notes = [n for n in notes if isinstance(n, BAD_SYNTAX_DETAILED)]
        self.assertTrue(detailed_notes, "BAD_SYNTAX_DETAILED was not raised")
        detail = str(detailed_notes[0].detail)
        self.assertIn("`", detail)
        self.assertNotIn("<script>", detail)

    def test_csd_present_keeps_code_span_formatting(self):
        """CSD_PRESENT's values are a closed vocabulary; MarkdownSafe-wrapping
        them must keep each one as its own code span, not plain-text prose."""
        notes = _response_notes([(b"Clear-Site-Data", b'"cache", "cookies"')])
        present_notes = [n for n in notes if isinstance(n, CSD_PRESENT)]
        self.assertTrue(present_notes, "CSD_PRESENT was not raised")
        detail = str(present_notes[0].detail)
        self.assertIn("<code>cache</code>", detail)
        self.assertIn("<code>cookies</code>", detail)


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

    def test_var_name_is_never_confused_with_a_prefix_of_another(self):
        """One var's name being a prefix of another's (e.g. "param" and
        "param_val") must not let the shorter name's placeholder match
        inside the longer name's placeholder text."""

        class NOTE_WITH_PREFIX_VARS(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "prefix collision test"
            _text = "%(param)s | %(param_val)s"

        notes = Notes({"field_name": "X-Test"})
        note = notes.add("test", NOTE_WITH_PREFIX_VARS, param="short", param_val="long-value")
        detail = str(note.detail)
        self.assertIn("short", detail)
        self.assertIn("long-value", detail)
        self.assertNotIn("short-value", detail)

    def test_empty_value_does_not_leave_a_stray_paragraph(self):
        """A wire-supplied var that's the empty string has nothing to
        protect, and shouldn't give Markdown placeholder text to wrap in
        a paragraph that becomes empty once the real (empty) value lands."""
        note = self._make(a="", b="")
        detail = str(note.detail)
        self.assertNotIn("<p></p>", detail)


# ---------------------------------------------------------------------------
# Regression tests from a follow-up multi-agent review of this branch
# (see PR #160 comments): markdown_context() only indented the first line
# of a wire excerpt, so an excerpt containing its own raw newline (e.g.
# from a decoded Structured Field Byte Sequence) broke out of the indented
# block early and let raw HTML reach ordinary, unescaped paragraph text.
# check_sf_params() crashed outright on a valid false-valued boolean param
# whose description has no %s to fill.
# ---------------------------------------------------------------------------

class EmbeddedNewlineTest(unittest.TestCase):
    """A wire value containing a raw newline must not break out of the
    indented block or inline span it's meant to be confined to."""

    def test_structured_field_parse_error_excerpt_with_newline_is_escaped(self):
        payload = b'"unterm\n<script>alert(1)</script>inated'
        notes = _response_notes([(b"Accept-CH", payload)])
        parse_error_notes = [n for n in notes if isinstance(n, STRUCTURED_FIELD_PARSE_ERROR)]
        self.assertTrue(parse_error_notes, "STRUCTURED_FIELD_PARSE_ERROR was not raised")
        detail = str(parse_error_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)

    def test_bad_syntax_detailed_excerpt_with_newline_is_escaped(self):
        notes = _request_notes([(b"Trailer", b"abc\n<script>alert(1)</script>@ghi")])
        detailed_notes = [n for n in notes if isinstance(n, BAD_SYNTAX_DETAILED)]
        self.assertTrue(detailed_notes, "BAD_SYNTAX_DETAILED was not raised")
        detail = str(detailed_notes[0].detail)
        self.assertNotIn("<script>", detail)

    def test_cache_status_byte_sequence_target_with_newline_is_escaped(self):
        """A Structured Field Byte Sequence target decodes to arbitrary
        bytes, including raw newlines -- not just backticks."""
        # base64 of "evil\n\n<script>alert(1)</script>"
        payload = b":ZXZpbAoKPHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==:; hit"
        notes = _response_notes([(b"Cache-Status", payload)])
        cache_status_notes = [n for n in notes if isinstance(n, CACHE_STATUS)]
        self.assertTrue(cache_status_notes, "CACHE_STATUS was not raised")
        detail = str(cache_status_notes[0].detail)
        self.assertNotIn("<script>", detail)
        self.assertIn("&lt;script&gt;", detail)


class CheckSfParamsFalsyBooleanTest(unittest.TestCase):
    """A valid, falsy Structured Field boolean param (e.g. hit=?0) for a
    param whose desc has no %s must not crash string formatting."""

    def test_cache_status_false_boolean_param_does_not_crash(self):
        notes = _response_notes([(b"Cache-Status", b"ExampleCache; hit=?0")])
        cache_status_notes = [n for n in notes if isinstance(n, CACHE_STATUS)]
        self.assertTrue(cache_status_notes, "CACHE_STATUS was not raised")
        detail = str(cache_status_notes[0].detail)
        self.assertNotIn("hit", detail.lower().split("examplecache")[-1])


class FormatSpecOnRealValueTest(unittest.TestCase):
    """A %(name)... directive with a width/precision must apply that spec
    to the real value, not to the opaque placeholder standing in for it.

    Found via a side-by-side port of this fix to redbot: the placeholder
    (a random nonce plus a counter) is long enough that a plausible
    precision spec, e.g. %(name).40s, could slice through it before its
    closing delimiter. That corrupts the token so the post-render
    substitution can no longer find it -- the real value is silently
    dropped, and a fragment of the placeholder leaks into the note
    instead. No template in this repo does this today, but the mechanism
    must handle it correctly regardless.
    """

    class NOTE_WITH_PRECISION(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "x"
        _text = "sample starts with: %(chunk_sample).40s"

    def test_precision_spec_truncates_the_real_value_not_the_placeholder(self):
        notes = Notes({"field_name": "X-Test"})
        note = notes.add("test", self.NOTE_WITH_PRECISION, chunk_sample="A" * 145)
        detail = str(note.detail)
        self.assertIn("A" * 40, detail)
        self.assertNotIn("A" * 41, detail)
        # A dropped/corrupted value would leak a hex nonce fragment instead.
        self.assertNotIn("chunk_sample", detail)

    def test_precision_spec_still_escapes_html(self):
        notes = Notes({"field_name": "X-Test"})
        note = notes.add(
            "test", self.NOTE_WITH_PRECISION, chunk_sample="<script>alert(1)</script>" * 3
        )
        detail = str(note.detail)
        self.assertNotIn("<script>", detail)

    def test_integer_spec_formats_the_real_int(self):
        class NOTE_WITH_INT_SPEC(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "x"
            _text = "count: %(n)05d"

        notes = Notes({"field_name": "X-Test"})
        note = notes.add("test", NOTE_WITH_INT_SPEC, n=42)
        self.assertIn("00042", str(note.detail))

    def test_markdown_safe_value_with_bare_directive_is_unaffected(self):
        class NOTE_WITH_SAFE_LIST(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "x"
            _text = "list:\n\n%(items)s"

        notes = Notes({"field_name": "X-Test"})
        note = notes.add(
            "test", NOTE_WITH_SAFE_LIST, items=MarkdownSafe("- `a`\n- `b`")
        )
        detail = str(note.detail)
        self.assertIn("<code>a</code>", detail)
        self.assertIn("<code>b</code>", detail)


# ---------------------------------------------------------------------------
# Unit tests: Note._translate is an overridable hook (downstream i18n)
# ---------------------------------------------------------------------------

class NoteTranslateHookTest(unittest.TestCase):
    """
    A downstream subclass (e.g. redbot's RedbotNote) can override
    _translate() to look messages up in its own catalog, without
    reimplementing _get_summary/_get_detail.
    """

    def test_default_translate_uses_httplint_catalog(self):
        with mock.patch(
            "httplint.note.translate", side_effect=lambda msg: f"[httplint] {msg}"
        ) as mocked:
            note = Notes({}).add("test", NOTE_WITH_PLAIN_VALUE, value="x")
            self.assertIn("[httplint] Unknown value", str(note.summary))
            mocked.assert_any_call(NOTE_WITH_PLAIN_VALUE._summary)

    def test_overridden_translate_is_used_for_summary_and_detail(self):
        class DOWNSTREAM_NOTE(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "Original summary."
            _text = "Original detail."

            def _translate(self, message: str) -> str:
                return message.replace("Original", "Downstream")

        note = Notes({}).add("test", DOWNSTREAM_NOTE)
        self.assertEqual(str(note.summary), "Downstream summary.")
        self.assertIn("Downstream detail.", str(note.detail))


# ---------------------------------------------------------------------------
# Unit tests: format TypeErrors are wrapped with diagnostics (#163)
# ---------------------------------------------------------------------------

class FormatErrorDiagnosticsTest(unittest.TestCase):
    """A bad %-directive (e.g. from a mistranslated catalog entry) must raise
    a TypeError naming the Note subclass, active locale, original error and
    vars -- not a bare, context-free error. Covers every exception type the
    %-operator can raise against a mistranslated template: TypeError,
    ValueError, KeyError, OverflowError."""

    class NOTE_WITH_BAD_INT_SPEC(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "count: %(count)d"
        _text = "count: %(count)d"

    class NOTE_WITH_BAD_CONVERSION(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "bad conversion: %(x)y"
        _text = "bad conversion: %(x)y"

    class NOTE_WITH_MISSING_VAR(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "missing: %(missing)s"
        _text = "missing: %(missing)s"

    class NOTE_WITH_CHAR_SPEC(Note):
        category = categories.GENERAL
        level = levels.WARN
        _summary = "char: %(n)c"
        _text = "char: %(n)c"

    def _make(self, note_cls, **vars):
        notes = Notes({"field_name": "X-Test"})
        return notes.add("test", note_cls, **vars)

    def _assert_wrapped(self, note, attr, kind):
        with self.assertRaises(TypeError) as ctx:
            getattr(note, attr)
        message = str(ctx.exception)
        self.assertIn(f"{kind} formatting error", message)
        self.assertIn(note.__class__.__name__, message)
        self.assertIn("locale:", message)
        return ctx.exception

    def test_summary_type_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_BAD_INT_SPEC, count="not-a-number")
        err = self._assert_wrapped(note, "summary", "Summary")
        self.assertIn("not-a-number", str(err))
        self.assertIsInstance(err.__cause__, TypeError)

    def test_detail_type_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_BAD_INT_SPEC, count="not-a-number")
        err = self._assert_wrapped(note, "detail", "Detail")
        self.assertIn("not-a-number", str(err))
        self.assertIsInstance(err.__cause__, TypeError)

    def test_summary_value_error_is_wrapped_with_diagnostics(self):
        """A conversion character _DIRECTIVE_RE doesn't recognise (so
        _get_detail's placeholder mechanism never touches it) still reaches
        the raw %-operator in both summary and detail."""
        note = self._make(self.NOTE_WITH_BAD_CONVERSION, x=MarkdownSafe("val"))
        err = self._assert_wrapped(note, "summary", "Summary")
        self.assertIsInstance(err.__cause__, ValueError)

    def test_detail_value_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_BAD_CONVERSION, x=MarkdownSafe("val"))
        err = self._assert_wrapped(note, "detail", "Detail")
        self.assertIsInstance(err.__cause__, ValueError)

    def test_summary_key_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_MISSING_VAR)
        err = self._assert_wrapped(note, "summary", "Summary")
        self.assertIsInstance(err.__cause__, KeyError)

    def test_detail_key_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_MISSING_VAR)
        err = self._assert_wrapped(note, "detail", "Detail")
        self.assertIsInstance(err.__cause__, KeyError)

    def test_summary_overflow_error_is_wrapped_with_diagnostics(self):
        """%(n)c with a value outside range(0x110000) raises OverflowError,
        not TypeError."""
        note = self._make(self.NOTE_WITH_CHAR_SPEC, n=0x110000)
        err = self._assert_wrapped(note, "summary", "Summary")
        self.assertIsInstance(err.__cause__, OverflowError)

    def test_detail_overflow_error_is_wrapped_with_diagnostics(self):
        note = self._make(self.NOTE_WITH_CHAR_SPEC, n=0x110000)
        err = self._assert_wrapped(note, "detail", "Detail")
        self.assertIsInstance(err.__cause__, OverflowError)

    def test_vars_repr_failure_does_not_swallow_diagnostic(self):
        """A var whose __repr__ raises must not destroy the diagnostic
        message -- the wrapper falls back to a placeholder instead of
        letting the repr() failure replace the real formatting error."""

        class Unrepresentable:
            def __repr__(self):
                raise RuntimeError("boom")

        note = self._make(self.NOTE_WITH_BAD_INT_SPEC, count=Unrepresentable())
        err = self._assert_wrapped(note, "summary", "Summary")
        self.assertIn("repr(vars) failed", str(err))
        self.assertIsInstance(err.__cause__, TypeError)

    def test_translate_override_error_is_wrapped_with_translation_diagnostics(self):
        """An error raised by an overridden _translate() gets its own
        diagnostic wrapping (class, locale) -- distinct from a %-formatting
        error, since a broken translation lookup is a different failure
        mode than a bad template and shouldn't be mislabeled as one."""

        class BROKEN_TRANSLATE_NOTE(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "x"
            _text = "x"

            def _translate(self, message):
                raise TypeError("can only concatenate str (not int) to str")

        note = self._make(BROKEN_TRANSLATE_NOTE)
        with self.assertRaises(TypeError) as ctx:
            note.summary  # pylint: disable=pointless-statement
        message = str(ctx.exception)
        self.assertIn("Translation error", message)
        self.assertIn("BROKEN_TRANSLATE_NOTE", message)
        self.assertIn("locale:", message)
        self.assertNotIn("formatting error", message)
        self.assertIsInstance(ctx.exception.__cause__, TypeError)

        with self.assertRaises(TypeError) as ctx2:
            note.detail  # pylint: disable=pointless-statement
        message2 = str(ctx2.exception)
        self.assertIn("Translation error", message2)
        self.assertNotIn("formatting error", message2)
        self.assertIsInstance(ctx2.exception.__cause__, TypeError)

    def test_translate_override_non_type_error_is_wrapped_and_chained(self):
        """_translate() isn't limited to raising TypeError -- an arbitrary
        exception type from a downstream override must still be coerced to
        a diagnostic TypeError, with the original preserved as __cause__."""

        class BROKEN_TRANSLATE_VALUE_ERROR(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "x"
            _text = "x"

            def _translate(self, message):
                raise ValueError("catalog lookup failed")

        note = self._make(BROKEN_TRANSLATE_VALUE_ERROR)
        with self.assertRaises(TypeError) as ctx:
            note.summary  # pylint: disable=pointless-statement
        message = str(ctx.exception)
        self.assertIn("Translation error", message)
        self.assertIn("catalog lookup failed", message)
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_translate_override_broken_str_does_not_swallow_diagnostic(self):
        """An exception from _translate() whose own __str__ raises must not
        destroy the diagnostic -- the wrapper falls back to a placeholder
        instead of letting the str() failure replace the real error, and
        the original (broken-str) exception is still chained as __cause__."""

        class BrokenStr(Exception):
            def __str__(self):
                raise RuntimeError("str exploded")

        class BROKEN_TRANSLATE_BROKEN_STR(Note):
            category = categories.GENERAL
            level = levels.WARN
            _summary = "x"
            _text = "x"

            def _translate(self, message):
                raise BrokenStr("unused")

        note = self._make(BROKEN_TRANSLATE_BROKEN_STR)
        with self.assertRaises(TypeError) as ctx:
            note.summary  # pylint: disable=pointless-statement
        message = str(ctx.exception)
        self.assertIn("Translation error", message)
        self.assertIn("str(err) failed", message)
        self.assertIsInstance(ctx.exception.__cause__, BrokenStr)

    def test_detail_rendering_error_is_wrapped_with_diagnostics(self):
        """A failure in the Markdown-conversion step itself (not just the
        %-formatting before it) must also get diagnostic context, rather
        than propagating as a bare, contextless exception."""
        note = self._make(self.NOTE_WITH_BAD_INT_SPEC, count=1)
        with mock.patch("httplint.note._get_markdown") as mock_get_markdown:
            mock_get_markdown.return_value.reset.return_value.convert.side_effect = (
                RuntimeError("markdown blew up")
            )
            with self.assertRaises(TypeError) as ctx:
                note.detail  # pylint: disable=pointless-statement
        message = str(ctx.exception)
        self.assertIn("Detail rendering error", message)
        self.assertIn(note.__class__.__name__, message)
        self.assertIn("locale:", message)
        self.assertNotIn("formatting error", message)
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
