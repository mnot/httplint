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

        The resulting string is already HTML-encoded. A MarkdownSafe value
        is substituted into the Markdown source before rendering, so it can
        appear in prose, code spans or link targets like ordinary template
        text -- that's an explicit, per-value opt-in made by the library
        code that composed it (see MarkdownSafe).

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
            else:
                str_val = str(val)
                if not str_val:
                    # Nothing to protect, and substituting a placeholder
                    # for it would give Markdown non-empty text to wrap in
                    # a stray <p></p> once the (empty) value replaces it.
                    render_vars[name] = ""
                    continue
                # \ue000 (Private Use Area) delimits each end so one var's
                # token can never be a prefix of another's (e.g. "param" vs
                # "param_val") -- do not remove these escapes, even though
                # they look like nothing changed in a diff or editor.
                token = f"\ue000{nonce}:{name}\ue000"
                placeholders[token] = str_val
                render_vars[name] = token

        html = _get_markdown().reset().convert(translate(self._text) % render_vars)
        if placeholders:
            pattern = re.compile("|".join(re.escape(token) for token in placeholders))
            html = pattern.sub(lambda m: str(escape(placeholders[m.group(0)])), html)
        return Markup(html)

    summary = property(_get_summary)
    detail = property(_get_detail)
