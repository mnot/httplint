import codecs
import hashlib
import re
from typing import Optional, Any, Dict, TypedDict
from typing_extensions import Unpack, NotRequired

from httplint.cache import ResponseCacheChecker
from httplint.content_encoding import ContentEncodingProcessor
from httplint.field.section import FieldSection
from httplint.note import Notes, Note, levels, categories
from httplint.syntax import rfc3986
from httplint.types import RawFieldListType
from httplint.util import iri_to_uri, f_num


class HttpMessageParams(TypedDict):
    start_time: NotRequired[Optional[float]]
    message_ref: NotRequired[Optional[str]]
    related: NotRequired["HttpMessageLinter"]


class HttpMessageLinter:
    """
    Base class for HTTP message linters.
    """

    message_ref = "This message"
    message_type = "message"

    def __init__(
        self,
        start_time: Optional[float] = None,
        message_ref: Optional[str] = None,
        related: Optional["HttpMessageLinter"] = None,
    ) -> None:
        self.notes = Notes({"message": message_ref or self.message_ref})
        self.related = related
        self.start_time = start_time
        self.finish_time: Optional[float] = None

        self.version: str = ""
        self.base_uri: str = ""
        self.headers = FieldSection(self)
        self.trailers = FieldSection(self)

        self.content_length: int = 0
        self.content_hash: Optional[bytes] = None
        self._hash_processor = hashlib.new("md5")
        self.decoded = ContentEncodingProcessor(self)
        self.character_encoding: Optional[str] = None

        self.transfer_length: int = 0
        self.complete: bool = False

    def process_request_topline(
        self, method: bytes, iri: bytes, version: bytes
    ) -> None:
        ...

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: Optional[bytes] = None
    ) -> None:
        ...

    def process_headers(self, headers: RawFieldListType) -> None:
        """
        Feed a list of (bytes name, bytes value) header tuples in and process them.
        """
        self.headers.process(headers)

        # set the character encoding from headers
        if "content-type" in self.headers.parsed:
            enc = self.headers.parsed["content-type"][1].get("charset", None)
            try:
                codecs.lookup(enc)
                self.character_encoding = enc
            except (LookupError, TypeError):
                pass

    def feed_content(self, chunk: bytes) -> None:
        """
        Feed a chunk of the content in. Can be called 0 to many times.

        Each processor in content_processors will be run over the chunk.
        """
        self.content_length += len(chunk)
        self._hash_processor.update(chunk)
        self.decoded.feed_content(chunk)

    def finish_content(
        self, complete: bool, trailers: Optional[RawFieldListType] = None
    ) -> None:
        """
        Signal that the content is done. Complete should be True if we
        know it's complete according to message framing.
        """
        self.complete = complete
        self.content_hash = self._hash_processor.digest()
        if trailers:
            self.trailers.process(trailers)
        self.decoded.finish_content()

        if self.can_have_content():
            if "content-length" in self.headers.parsed:
                if self.content_length == self.headers.parsed["content-length"]:
                    self.notes.add("header-content-length", CL_CORRECT)
                else:
                    self.notes.add(
                        "header-content-length",
                        CL_INCORRECT,
                        content_length=f_num(self.content_length),
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
    message_ref = "This request"
    messsage_type = "request"

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.method: Optional[str] = None
        self.iri: Optional[str] = None
        self.uri: Optional[str] = None

    def process_request_topline(
        self, method: bytes, iri: bytes, version: bytes
    ) -> None:
        self.method = method.decode("ascii", "replace")
        self.set_uri(iri.decode("utf-8", "replace"))
        self.version = version.decode("ascii", "replace")

    def set_uri(self, iri: str) -> None:
        """
        Given a unicode string (possibly an IRI), convert to a URI and make sure it's sensible.
        """
        self.iri = iri
        try:
            self.uri = iri_to_uri(iri)
        except (ValueError, UnicodeError):
            self.notes.add("uri", URI_BAD_SYNTAX)
            self.uri = iri  # hope?
            return
        if not re.match(rf"^\s*{rfc3986.URI}\s*$", self.uri, re.VERBOSE):
            self.notes.add("uri", URI_BAD_SYNTAX)
        if "#" in self.uri:
            # chop off the fragment
            self.uri = self.uri[: self.uri.index("#")]
        if len(self.uri) > self.max_uri_chars:
            self.notes.add("uri", URI_TOO_LONG, uri_len=f_num(len(self.uri)))


class HttpResponseLinter(HttpMessageLinter):
    """
    A HTTP Response message linter.
    """

    message_ref = "This response"
    message_type = "response"

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.status_code_str: Optional[str] = None
        self.status_code: Optional[int] = None
        self.status_phrase: Optional[str] = None
        self.is_head_response = False
        self.caching: ResponseCacheChecker

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: Optional[bytes] = None
    ) -> None:
        self.version = version.decode("ascii", "replace")
        self.status_code_str = status_code.decode("ascii", "replace")
        try:
            self.status_code = int(self.status_code_str)
        except ValueError:
            self.notes.add("status", STATUS_CODE_NON_NUMERIC)
        if status_phrase:
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
        self.caching = ResponseCacheChecker(self)


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
    _summary = "%(message)s's Content-Length header is incorrect."
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


class STATUS_CODE_NON_NUMERIC(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The status code is not an integer."
    _text = """\
This isn't a valid status code; it needs to be an ASCII integer."""


class STATUS_PHRASE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The status phrase contains non-ASCII characters."
    _text = """\
The status phrase can only contain ASCII characters."""
