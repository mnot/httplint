from collections import UserList
from enum import Enum
from typing import Any, MutableMapping, Dict, Type, List, Optional

from markupsafe import Markup, escape
from markdown import Markdown

from httplint.types import VariableType
from httplint.i18n import translate, L_


class categories(Enum):
    "Note classifications."

    GENERAL = L_("General")
    SECURITY = L_("Browser Security")
    COOKIES = L_("Cookies")
    CONNEG = L_("Content Negotiation")
    CACHING = L_("Caching")
    VALIDATION = L_("Validation")
    CONNECTION = L_("Connection")
    RANGE = L_("Partial Content")
    CORS = L_("Cross-Origin Resource Sharing")


class levels(Enum):
    "Note levels."

    GOOD = "good"
    WARN = "warning"
    BAD = "bad"
    INFO = "info"


class Notes(UserList):
    """
    A list of notes.
    """

    def __init__(self, default_vars: Dict[str, VariableType]):
        UserList.__init__(self)
        self._default_vars = default_vars

    def add(
        self,
        subject: str,
        note: Type["Note"],
        category: Optional[categories] = None,
        **vrs: VariableType,
    ) -> "Note":
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
    _markdown = Markdown(output_format="html")

    def __init__(self, subject: str, **vrs: VariableType) -> None:
        self.subject = subject
        self.vars = vrs or {}
        self.subnotes: List["Note"] = []

    def add_child(self, note: Type["Note"], **vrs: VariableType) -> "Note":
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

    def _get_summary(self) -> Markup:
        """
        Output a textual summary of the message as a Unicode string.

        Note that if it is displayed in an environment that needs
        encoding (e.g., HTML), that is *NOT* done.
        """
        return Markup(translate(self._summary) % self.vars)

    def _get_detail(self) -> Markup:
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded.
        """
        return Markup(
            self._markdown.reset().convert(
                translate(self._text) % {k: escape(v) for k, v in self.vars.items()}
            )
        )

    summary = property(_get_summary)
    detail = property(_get_detail)
