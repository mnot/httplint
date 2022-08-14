from enum import Enum
from typing import Any, Union, Type, List

from markupsafe import Markup, escape
from markdown import markdown


class categories(Enum):
    "Note classifications."
    GENERAL = "General"
    SECURITY = "Security"
    CONNEG = "Content Negotiation"
    CACHING = "Caching"
    VALIDATION = "Validation"
    CONNECTION = "Connection"
    RANGE = "Partial Content"


class levels(Enum):
    "Note levels."
    GOOD = "good"
    WARN = "warning"
    BAD = "bad"
    INFO = "info"


class Notes:
    """
    A list of notes.
    """

    default_vars = {
        "response": "This response"
    }

    def __init__(self) -> None:
        self.notes: List[Note] = []

    def add(self, subject: str, note: Type["Note"], **vrs: Union[str, int]) -> None:
        tmp_vars = self.default_vars.copy()
        tmp_vars.update(vrs)
        self.notes.append(note(subject, **tmp_vars))


class Note:
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.

    The summary field is automatically HTML escaped, so it can contain arbitrary text.

    However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated
    into it need to be escaped to be safe for use in HTML.
    """

    category: categories = None
    level: levels = None
    summary = ""
    text = ""

    def __init__(self, subject: str, **vrs: Union[str, int]) -> None:
        self.subject = subject
        self.vars = vrs or {}

    def __str__(self):
        return self.show_summary('en')

    def __eq__(self, other: Any) -> bool:
        return bool(
            self.__class__ == other.__class__
            and self.vars == other.vars
            and self.subject == other.subject
        )

    def show_summary(self, lang: str) -> Markup:
        """
        Output a textual summary of the message as a Unicode string.

        Note that if it is displayed in an environment that needs
        encoding (e.g., HTML), that is *NOT* done.
        """
        return Markup(self.summary % self.vars)

    def show_text(self, lang: str) -> Markup:
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded.
        """
        return Markup(
            markdown(
                self.text % {k: escape(str(v)) for k, v in self.vars.items()},
                output_format="html",
            )
        )
