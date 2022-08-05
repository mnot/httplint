import re

from .message import HttpMessage
from .note import Note, categories, levels
from .syntax import rfc3986
from .util import iri_to_uri, f_num


class HttpRequest(HttpMessage):
    """
    A HTTP Request message.
    """

    max_uri_chars = 8000

    def __init__(
        self,
    ) -> None:
        HttpMessage.__init__(self)
        self.method = None  # type: str
        self.iri = None  # type: str
        self.uri = None  # type: str

    def process_top_line(self, line: bytes) -> None:
        pass

    def set_iri(self, iri: str) -> None:
        """
        Given a unicode string (possibly an IRI), convert to a URI and make sure it's sensible.
        """
        self.iri = iri
        try:
            self.uri = iri_to_uri(iri)
        except (ValueError, UnicodeError):
            self.notes.add("uri", URI_BAD_SYNTAX)
        if not re.match(rf"^\s*{rfc3986.URI}\s*$", self.uri, re.VERBOSE):
            self.notes.add("uri", URI_BAD_SYNTAX)
        if "#" in self.uri:
            # chop off the fragment
            self.uri = self.uri[: self.uri.index("#")]
        if len(self.uri) > self.max_uri_chars:
            self.notes.add("uri", URI_TOO_LONG, uri_len=f_num(len(self.uri)))


class URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The URI is very long (%(uri_len)s characters)."
    text = """\
Long URIs aren't supported by some implementations, including proxies. A reasonable upper size
limit is 8192 characters."""


class URI_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The URI's syntax isn't valid."
    text = """\
This isn't a valid URI. Look for illegal characters and other problems; see
[RFC3986](http://www.ietf.org/rfc/rfc3986.txt) for more information."""
