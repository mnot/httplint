import hashlib
import re
from typing import Any, List, Dict, Tuple, TypedDict
from typing_extensions import Unpack, NotRequired

from httplint.cache import ResponseCacheChecker
from httplint.content_encoding import ContentEncodingProcessor
from httplint.field_section import FieldSection
from httplint.note import Notes, Note, levels, categories
from httplint.syntax import rfc3986
from httplint.types import RawFieldListType
from httplint.util import iri_to_uri, f_num


class HttpMessageParams(TypedDict):
    start_time: NotRequired[int]
    notes: NotRequired[Notes]
    related: NotRequired["HttpMessageLinter"]
    max_sample_size: NotRequired[int]


class HttpMessageLinter:
    """
    Base class for HTTP message linters.
    """

    def __init__(
        self,
        start_time: int = None,
        notes: Notes = None,
        related: "HttpMessageLinter" = None,
        max_sample_size: int = 1024,
    ) -> None:
        self.notes = notes or Notes()
        self.related = related
        self.start_time: int = start_time
        self.max_sample_size = max_sample_size  # biggest sample, in bytes. 0 to disable

        self.version: str = ""
        self.base_uri: str = ""
        self.headers = FieldSection()
        self.trailers = FieldSection()

        self.content_sample: List[Tuple[int, bytes]] = []
        self.content_len: int = 0
        self.content_hash: bytes = None
        self._hash_processor = hashlib.new("md5")
        self.content_processors = [ContentEncodingProcessor(self)]

        self.transfer_length: int = 0
        self.complete: bool = False

    def process_request_topline(
        self, method: bytes, iri: bytes, version: bytes
    ) -> None:
        ...

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: bytes = None
    ) -> None:
        ...

    def process_headers(self, headers: RawFieldListType) -> None:
        """
        Feed a list of (bytes name, bytes value) header tuples in and process them.
        """
        self.headers.process(headers, self)

    def feed_content(self, chunk: bytes) -> None:
        """
        Feed a chunk of the content in. Can be called 0 to many times.

        Each processor in content_processors will be run over the chunk.
        """
        if self.content_len < self.max_sample_size:
            self.content_sample.append((self.content_len, chunk))
        self.content_len += len(chunk)
        self._hash_processor.update(chunk)
        for processor in self.content_processors:
            processor.feed_content(chunk)

    def finish_content(self, complete: bool, trailers: RawFieldListType = None) -> None:
        """
        Signal that the content is done. Complete should be True if we
        know it's complete according to message framing.
        """
        self.complete = complete
        self.content_hash = self._hash_processor.digest()
        if trailers:
            self.trailers.process(trailers, self)

        for processor in self.content_processors:
            processor.finish_content()

        if self.can_have_content():
            if "content-length" in self.headers.parsed:
                if self.content_len == self.headers.parsed["content-length"]:
                    self.notes.add("header-content-length", CL_CORRECT)
                else:
                    self.notes.add(
                        "header-content-length",
                        CL_INCORRECT,
                        content_length=f_num(self.content_len),
                    )
        self.post_checks()

    def can_have_content(self) -> bool:
        "Say whether this message can have content."
        return True

    def post_checks(self) -> None:
        "Post-parsing checks to perform."

    def __repr__(self) -> str:
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        return f"<{', '.join(status)} at {id(self):#x}>"

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = self.__dict__.copy()
        for key in [
            "_hash_processor",
        ]:
            if key in state:
                del state[key]
        return state


class HttpRequestLinter(HttpMessageLinter):
    """
    A HTTP Request message linter.
    """

    max_uri_chars = 8000

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.method: str = None
        self.iri: str = None
        self.uri: str = None

    def process_request_topline(
        self, method: bytes, iri: bytes, version: bytes
    ) -> None:
        self.method = method.decode("ascii", "replace")
        self.iri = iri.decode("utf-8", "replace")
        self.uri = self.set_uri(self.iri)
        self.version = version.decode("ascii", "replace")

    def set_uri(self, iri: str) -> str:
        """
        Given a unicode string (possibly an IRI), convert to a URI and make sure it's sensible.
        """
        uri = None
        try:
            uri = iri_to_uri(iri)
        except (ValueError, UnicodeError):
            self.notes.add("uri", URI_BAD_SYNTAX)
        if not re.match(rf"^\s*{rfc3986.URI}\s*$", self.uri, re.VERBOSE):
            self.notes.add("uri", URI_BAD_SYNTAX)
        if "#" in self.uri:
            # chop off the fragment
            uri = self.uri[: self.uri.index("#")]
        if len(self.uri) > self.max_uri_chars:
            self.notes.add("uri", URI_TOO_LONG, uri_len=f_num(len(self.uri)))
        return uri


class HttpResponseLinter(HttpMessageLinter):
    """
    A HTTP Response message linter.
    """

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.status_code: int = None
        self.status_phrase: str = ""
        self.is_head_response = False

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: bytes = None
    ) -> None:
        self.version = version.decode("ascii", "replace")
        try:
            self.status_code = int(status_code.decode("ascii", "replace"))
        except UnicodeDecodeError:
            pass
        except ValueError:
            pass
        try:
            self.status_phrase = status_phrase.decode("ascii", "strict")
        except UnicodeDecodeError:
            self.status_phrase = status_phrase.decode("ascii", "replace")
            self.notes.add("status", STATUS_PHRASE_ENCODING)

    def can_have_content(self) -> bool:
        if self.is_head_response:
            return False
        if self.status_code in [304]:
            return False
        return True

    def post_checks(self) -> None:
        ResponseCacheChecker(self)


class CL_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    _summary = "The Content-Length header is correct."
    _text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next."""


class CL_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "%(response)s's Content-Length header is incorrect."
    _text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. An incorrect `Content-Length` can cause security and intereoperablity
issues.

The actual content size was %(content_length)s bytes."""


class URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The URI is very long (%(uri_len)s characters)."
    _text = """\
Long URIs aren't supported by some implementations, including proxies. A reasonable upper size
limit is 8192 characters."""


class URI_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The URI's syntax isn't valid."
    _text = """\
This isn't a valid URI. See
[RFC3986](http://www.ietf.org/rfc/rfc3986.txt) for more information."""


class STATUS_PHRASE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The status phrase contains non-ASCII characters."
    _text = """\
The status phrase can only contain ASCII characters."""
