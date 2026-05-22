from __future__ import annotations

from collections import UserList
from enum import Enum
from threading import local
from typing import Any, Dict, MutableMapping, Optional, Type

from markdown import Markdown
from markupsafe import Markup

from httplint.i18n import L_, translate
from httplint.types import NoteListType, VariableType


class _MdLocal(local):
    md: Markdown


_md_local = _MdLocal()


class MarkdownSafe(str):
    """
    Marker for var values that are pre-composed Markdown.

    Note._get_detail strips backticks from interpolated var values so
    wire-supplied data cannot close a code span and inject raw HTML.
    Wrap a value in MarkdownSafe(...) when the backticks (or other
    Markdown syntax) in the value were produced by library code and
    must survive interpolation intact.
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

        The resulting string is already HTML-encoded.  Variable values are
        passed as plain strings; the Markdown renderer handles escaping.
        Template authors must wrap user-controlled vars in backtick code
        spans (or indented code blocks) so Markdown escapes them correctly.

        As defense-in-depth, backticks are stripped from each interpolated
        value so a wire-supplied backtick cannot close the surrounding
        code span and let the rest of the value render as raw HTML.
        Values that are pre-composed Markdown produced by library code
        (e.g. a joined list of code spans) should be wrapped in
        MarkdownSafe to opt out of this stripping.
        """
        def _coerce(val: Any) -> str:
            if isinstance(val, MarkdownSafe):
                return str(val)
            return str(val).replace("`", "")

        safe_vars = {k: _coerce(v) for k, v in self.vars.items()}
        return Markup(
            _get_markdown().reset().convert(translate(self._text) % safe_vars)
        )

    summary = property(_get_summary)
    detail = property(_get_detail)
