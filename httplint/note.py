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

    Note._get_detail treats every var as opaque, wire-supplied data --
    substituted into the rendered HTML only after Markdown has run,
    HTML-escaped, so it can never be parsed as Markdown syntax -- unless
    it's wrapped in MarkdownSafe(...). Wrap a value in MarkdownSafe(...)
    when it is pre-composed Markdown built by library code (e.g. a joined
    list of code spans, or an indented excerpt built by
    httplint.util.markdown_context) and must be rendered as Markdown
    rather than treated as opaque wire data. Never wrap a value that still
    contains unvetted wire content -- escape or strip each wire-derived
    fragment before assembling and wrapping it.
    """


def _get_markdown() -> Markdown:
    """Return a per-thread Markdown instance, creating it on first use."""
    if not hasattr(_md_local, "md"):
        _md_local.md = Markdown(output_format="html")
    return _md_local.md


# Matches a single %-format directive with a named key, e.g. %(name)s,
# %(name).40s, %(name)5d -- everything but the bare "%%" escape, which
# needs no key and is left for the final %-operator pass to collapse.
_DIRECTIVE_RE = re.compile(r"%\((\w+)\)([-+ #0]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa])")


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

    def _translate(self, message: str) -> str:
        """
        Look up `message` in the message catalog. Subclasses defined by
        downstream projects can override this to translate against their
        own catalog instead of httplint's.
        """
        return translate(message)

    def _get_summary(self) -> str:
        """
        Output a textual summary of the message as a plain-text string.

        The value is NOT HTML-escaped.  Consumers are responsible for escaping
        before embedding in HTML.
        """
        return self._translate(self._summary) % self.vars

    def _get_detail(self) -> Markup:
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded. A MarkdownSafe value
        is substituted into the Markdown source before rendering, so it can
        appear in prose, code spans or link targets like ordinary template
        text -- that's an explicit, per-value opt-in made by the library
        code that composed it (see MarkdownSafe).

        Every other var is wire-supplied: it is rendered as an opaque
        placeholder, and only substituted -- HTML-escaped -- into the
        rendered HTML afterwards. Such a value is therefore never parsed as
        Markdown, so backticks and other Markdown syntax in it survive and
        display literally, instead of being stripped or able to break out
        of a code span.

        A directive's width/precision (e.g. %(name).40s) is applied to the
        real value before it's hidden behind a placeholder, not to the
        placeholder itself -- the placeholder is long enough (a random
        nonce plus a counter) that a plausible width spec could otherwise
        slice through it, corrupting it so the post-render substitution
        below can no longer find it: the real value would be silently
        dropped and a fragment of the placeholder would leak into the
        rendered note instead.
        """
        nonce = secrets.token_hex(16)
        placeholders: Dict[str, str] = {}

        def _substitute_directive(directive: "re.Match[str]") -> str:
            name, spec = directive.group(1), directive.group(2)
            val = self.vars[name]
            if isinstance(val, MarkdownSafe):
                return directive.group(0)  # left for the % pass below
            formatted = ("%" + spec) % (val,)
            if not formatted:
                # Nothing to protect, and substituting a placeholder for
                # it would give Markdown non-empty text to wrap in a
                # stray <p></p> once the (empty) value replaces it.
                return ""
            # \ue000 (Private Use Area) delimits each end so one
            # directive's token can never be a prefix of another's -- do
            # not remove these escapes, even though they look like
            # nothing changed in a diff or editor.
            token = f"\ue000{nonce}:{len(placeholders)}\ue000"
            placeholders[token] = formatted
            return token

        templated = _DIRECTIVE_RE.sub(_substitute_directive, self._translate(self._text))
        safe_vars = {n: str(v) for n, v in self.vars.items() if isinstance(v, MarkdownSafe)}
        html = _get_markdown().reset().convert(templated % safe_vars)
        if placeholders:
            pattern = re.compile("|".join(re.escape(token) for token in placeholders))
            html = pattern.sub(lambda m: str(escape(placeholders[m.group(0)])), html)
        return Markup(html)

    summary = property(_get_summary)
    detail = property(_get_detail)
