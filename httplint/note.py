from __future__ import annotations

import re
import secrets
from collections import UserList
from enum import Enum
from threading import local
from typing import Any, Dict, MutableMapping, Optional, Type

from markdown import Markdown
from markupsafe import Markup, escape

from httplint.i18n import L_, translate
from httplint.types import NoteListType, VariableType


class _MdLocal(local):
    md: Markdown


_md_local = _MdLocal()


class MarkdownSafe(str):
    """
    Marker for var values that are pre-composed Markdown.

    Note._get_detail treats a var as opaque, wire-supplied data unless it is
    named in KNOWN_SAFE_VARS: opaque values are substituted into the
    rendered HTML only after Markdown has run, HTML-escaped, so they can
    never be parsed as Markdown syntax. Wrap a value in MarkdownSafe(...)
    when it is pre-composed Markdown produced by library code (e.g. a
    joined list of code spans) and must be rendered as Markdown rather than
    treated as opaque wire data.
    """


def _get_markdown() -> Markdown:
    """Return a per-thread Markdown instance, creating it on first use."""
    if not hasattr(_md_local, "md"):
        _md_local.md = Markdown(output_format="html")
    return _md_local.md


# ---------------------------------------------------------------------------
# Vars that are always controlled by the library, never by HTTP input.
#
# A var belongs here when ALL of the following are true:
#   1. Its value is computed or chosen by library code, not copied from the
#      wire (header name, header value, URI, etc.).
#   2. Its character set is provably HTML-safe — e.g. an integer, an
#      ISO-formatted date, a Python type name, or a string chosen from a
#      fixed set like {"request", "response"}.
#   3. OR it is pre-formatted by library code that already wraps the
#      user-facing portions in backtick spans (e.g. markdown_list / _make_list).
#
# These vars are substituted into the Markdown source before rendering, so
# they can appear in link targets (`](%(ref_uri)s)`) as well as prose. Every
# other var is treated as wire-supplied: Note._get_detail renders it as an
# opaque placeholder and only substitutes it — HTML-escaped — after Markdown
# has run, so it can never be parsed as Markdown syntax.
#
# If you add a new Note that uses one of these var names for *HTTP input*,
# remove the name from this set so the var goes through the wire-supplied path.
# ---------------------------------------------------------------------------

KNOWN_SAFE_VARS: frozenset[str] = frozenset(
    {
        # always supplied by the library, never from the wire
        "field_name",
        "subject",
        # library-computed cache ages / freshness lifetimes (human-readable strings)
        "current_age",
        "freshness_lifetime",
        "fresh_lifetime",
        "fresh_left",
        "share_lifetime",
        "share_left",
        # byte-count integers
        "content_length",
        "ok_brotli_len",
        "ok_zlib_len",
        "server_length",
        "set_cookie_value_length",
        # other numeric / constrained values
        "post_check",  # Cache-Control integer directive, validated before use
        "pre_check",  # Cache-Control integer directive, validated before use
        "duration",  # library-formatted duration (Max-Age / Expires)
        # library-formatted date strings (not raw wire values)
        "date",
        "last_modified_string",
        # library URIs (set as class attributes, not from the wire)
        "ref_uri",
        "deprecation_ref",
        # type-name strings chosen by the library ("string", "integer", …)
        "expected_type",
        "expected",
        "item_type",
        # fixed-vocabulary strings: "request" / "response"
        "message_type",
        "other_message",
        # HTTP request methods — constrained alphabet, no HTML special chars
        "method",
        # HTTP status codes — integers or short library-chosen phrases
        "status",
        # library-generated prose appended to report-only variants
        "report_only_text",
        # pre-formatted lists: markdown_list() / _make_list() already add backticks
        "conflicts",
        "directives_list",
        "headers",
        # Clear-Site-Data directive names: closed set ({cache, cookies, storage,
        # executionContexts, *}); each item is wrapped in a backtick span.
        "values",
        # Reporting-Endpoints names: SF dictionary keys (same alphabet as `key`);
        # each item is wrapped in a backtick span.
        "endpoints",
        # Set-Cookie cookie-name: attacker-controlled (loose_parse does not enforce
        # tchar). Library strips backticks before wrapping each name in a span; the
        # markdown renderer HTML-escapes <, >, & inside code spans, so the value
        # cannot escape the span.
        "cookie_names",
        # Link resource-hint markdown list: rel tokens are from a closed set; link
        # targets are attacker-controlled, but library strips backticks before
        # wrapping each target in a code span (see cookie_names justification).
        "detail_lines",
        # SF-constrained: missing Vary fields come from Accept-CH Tokens
        "missing_fields",
        # SF dict keys: [a-z0-9_\-.*] only, no HTML special chars
        "key",
        # "context" in DUPLICATE_KEY is a word like "inner" from http_sf;
        # "context" in STRUCTURED_FIELD_PARSE_ERROR is either "" or a 4-space
        # indented block that Markdown puts in a <pre> and escapes.
        "context",
        # HTTP parameter names follow token syntax; no < > & allowed
        "param",
        # library error messages with static text (not echoing wire values)
        "problem",  # RANGE_BAD_SYNTAX: all values are library string literals
        "details",  # NEL: all values are library string literals
    }
)


class categories(Enum):
    "Note classifications."

    GENERAL = L_("General")
    CONNECTION = L_("Connection")
    SECURITY = L_("Browser Security")
    CORS = L_("Cross-Origin Resource Sharing")
    COOKIES = L_("Cookies")
    CONNEG = L_("Content Negotiation")
    CACHING = L_("Caching")
    VALIDATION = L_("Validation")
    RANGE = L_("Partial Content")


class levels(Enum):
    "Note levels."

    GOOD = "good"
    WARN = "warning"
    BAD = "bad"
    INFO = "info"


class Notes(UserList[Any]):
    """
    A list of notes.
    """

    def __init__(self, default_vars: Dict[str, VariableType]):
        UserList.__init__(self)
        self._default_vars = default_vars

    def add(
        self,
        subject: str,
        note: Type[Note],
        category: Optional[categories] = None,
        **vrs: VariableType,
    ) -> Note:
        tmp_vars: MutableMapping[str, VariableType] = self._default_vars.copy()
        tmp_vars.update(vrs)
        new_note = note(subject, **tmp_vars)
        if category and new_note.category == categories.GENERAL:
            new_note.category = category
        self.data.append(new_note)
        return new_note


class Note:
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.

    The summary field is automatically HTML escaped, so it can contain arbitrary text.

    However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated
    into it need to be escaped to be safe for use in HTML.
    """

    category: categories
    level: levels
    _summary = ""
    _text = ""

    def __init__(self, subject: str, **vrs: VariableType) -> None:
        self.subject = subject
        self.vars = vrs or {}
        self.subnotes: NoteListType = []

    def add_child(self, note: Type[Note], **vrs: VariableType) -> Note:
        tmp_vars = self.vars.copy()
        tmp_vars.update(vrs)
        new_note = note(self.subject, **tmp_vars)
        self.subnotes.append(new_note)
        return new_note

    def __str__(self) -> str:
        return str(self.summary)

    def __eq__(self, other: Any) -> bool:
        return bool(
            self.__class__ == other.__class__
            and self.vars == other.vars
            and self.subject == other.subject
        )

    def _get_summary(self) -> str:
        """
        Output a textual summary of the message as a plain-text string.

        The value is NOT HTML-escaped.  Consumers are responsible for escaping
        before embedding in HTML.
        """
        return translate(self._summary) % self.vars

    def _get_detail(self) -> Markup:
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded.  MarkdownSafe values
        and vars named in KNOWN_SAFE_VARS are substituted into the Markdown
        source before rendering, so they can appear in prose, code spans or
        link targets like ordinary template text.

        Every other var is wire-supplied: it is rendered as an opaque
        placeholder, and only substituted — HTML-escaped — into the
        rendered HTML afterwards. Such a value is therefore never parsed as
        Markdown, so backticks and other Markdown syntax in it survive and
        display literally, instead of being stripped or able to break out
        of a code span.
        """
        nonce = secrets.token_hex(16)
        placeholders: Dict[str, str] = {}
        render_vars: Dict[str, str] = {}
        for name, val in self.vars.items():
            if isinstance(val, MarkdownSafe):
                render_vars[name] = str(val)
            elif name in KNOWN_SAFE_VARS:
                render_vars[name] = str(val).replace("`", "")
            else:
                token = f"{nonce}:{name}"
                placeholders[token] = str(val)
                render_vars[name] = token

        html = _get_markdown().reset().convert(translate(self._text) % render_vars)
        if placeholders:
            pattern = re.compile("|".join(re.escape(token) for token in placeholders))
            html = pattern.sub(lambda m: str(escape(placeholders[m.group(0)])), html)
        return Markup(html)

    summary = property(_get_summary)
    detail = property(_get_detail)
