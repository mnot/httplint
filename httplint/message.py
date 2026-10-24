import hashlib
import re
import weakref
from functools import partial
from typing import Any, Dict, Optional, TypedDict, cast
from urllib.parse import urlsplit

from typing_extensions import NotRequired, Unpack

from httplint.cache import ResponseCacheChecker
from httplint.charset import is_text_encoding, verify_charset, whatwg_encoding
from httplint.content_encoding import ContentEncodingProcessor
from httplint.content_type import verify_content_type
from httplint.field.cors import check_preflight_request, check_preflight_response
from httplint.field.section import FieldSection
from httplint.field.utils import parse_digits
from httplint.i18n import L_, translate
from httplint.note import Note, Notes, categories, levels
from httplint.status import StatusChecker
from httplint.syntax import rfc3986, rfc9112
from httplint.types import (
    CachingProtocol,
    LinterProtocol,
    NotesProtocol,
    RawFieldListType,
    RequestLinterProtocol,
    ResponseLinterProtocol,
    SectionProtocol,
)
from httplint.util import authority_to_ascii, f_num, iri_to_uri, userinfo_escape_growth


class HttpMessageParams(TypedDict):
    start_time: NotRequired[Optional[float]]
    _related: NotRequired[Optional[LinterProtocol]]
    no_content: NotRequired[bool]


class HttpMessageLinter:
    """
    Base class for HTTP message linters.

    ``start_time`` is when the exchange happened, in seconds since the epoch. If it is
    not given, time-dependent checks are skipped where they can be, but a two-digit year
    in an obsolete date is resolved against the time linting runs (RFC 9110 Section
    5.6.7), so the result for a year near the 50-year line depends on when it is run.
    """

    message_type = L_("message")

    @property
    def as_request(self) -> Optional[RequestLinterProtocol]:
        if self.message_type == "request":
            return cast(RequestLinterProtocol, self)
        return None

    @property
    def as_response(self) -> Optional[ResponseLinterProtocol]:
        if self.message_type == "response":
            return cast(ResponseLinterProtocol, self)
        return None

    def __init__(
        self,
        start_time: Optional[float] = None,
        _related: Optional[LinterProtocol] = None,
        no_content: bool = False,
    ) -> None:
        self.notes: NotesProtocol = Notes({"message_type": translate(self.message_type)})
        self._related = _related
        self.start_time = start_time
        self.finish_time: Optional[float] = None
        self.no_content = no_content

        self.version: str = ""
        self.base_uri: str = ""
        self.headers: SectionProtocol = FieldSection(self)
        self.trailers: SectionProtocol = FieldSection(self, is_trailer=True)

        self.content_length: int = 0
        self.content_hash: Optional[bytes] = None
        self._hash_processor = hashlib.new("md5", usedforsecurity=False)
        self.character_encoding: Optional[str] = None
        self.whatwg_encoding: Optional[str] = None
        self.content_sample: bytes = b""
        self.content_sample_truncated: bool = False

        self.transfer_length: int = 0
        self.complete: bool = False

        self.decoded = ContentEncodingProcessor(self)
        self_ref = weakref.ref(self)

        def weak_content_sample_processor(chunk: bytes) -> None:
            obj = self_ref()
            if obj is not None:
                obj._content_sample_processor(chunk)  # pylint: disable=protected-access

        self.decoded.processors.append(weak_content_sample_processor)

    def process_request_topline(self, method: bytes, iri: bytes, version: bytes) -> None: ...

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: Optional[bytes] = None
    ) -> None: ...

    def process_headers(self, headers: RawFieldListType) -> None:
        """
        Feed a list of (bytes name, bytes value) header tuples in and process them.
        """
        self.headers.process(headers)

        # set the character encoding from headers
        if "content-type" in self.headers.parsed:
            enc = self.headers.parsed["content-type"][1].get("charset", None)
            self.whatwg_encoding = whatwg_encoding(enc)
            # Python has to be able to decode it too: consumers pass this straight to
            # the codec machinery, and 'replacement' labels are ones recipients refuse.
            if self.whatwg_encoding not in (None, "replacement") and is_text_encoding(enc):
                self.character_encoding = enc

    def feed_content(self, chunk: bytes) -> None:
        """
        Feed a chunk of the content in. Can be called 0 to many times.

        Each processor in content_processors will be run over the chunk.
        """
        self.content_length += len(chunk)
        if not self.no_content:
            self._hash_processor.update(chunk)
            self.decoded.feed_content(chunk)

    def finish_content(self, complete: bool, trailers: Optional[RawFieldListType] = None) -> None:
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
            if "content-length" in self.headers.parsed and not self.no_content:
                if self.content_length == self.headers.parsed["content-length"]:
                    self.notes.add("field-content-length", CL_CORRECT)
                else:
                    self.notes.add(
                        "field-content-length",
                        CL_INCORRECT,
                        content_length=f_num(self.content_length),
                    )
        else:
            if self.content_length and not self.no_content and not self.is_connect_tunnel():
                self.notes.add(
                    "message", CONTENT_NOT_ALLOWED, message=translate(L_("This message"))
                )
        self.post_checks()

        for section in [self.headers, self.trailers]:
            for handler in section.handlers.values():
                field_add_note = partial(
                    self.notes.add,
                    f"field-{handler.canonical_name.lower()}",
                    field_name=handler.canonical_name,
                    field_type=section.is_trailer and L_("trailer") or L_("header"),
                )
                if handler.value is not None:
                    handler.post_check(field_add_note)

    def can_have_content(self) -> bool:
        "Say whether this message can have content."
        return True

    def is_connect_tunnel(self) -> bool:
        "Say whether the bytes after the header section are tunnel data, not content."
        return False

    def has_full_representation(self) -> bool:
        "Say whether this message's content is a full representation of the resource."
        return self.can_have_content()

    @property
    def content_decoded(self) -> bool:
        "Say whether the content coding(s) were undone, so the content is available to check."
        return self.decoded.content_available

    def post_checks(self) -> None:
        "Post-parsing checks to perform."

    content_sample_size = 8192

    def _content_sample_processor(self, chunk: bytes) -> None:
        """
        Capture a sample of the decoded content, noting whether it had to
        be cut short so charset checks know it may end mid-character even
        when the full content doesn't.

        Nothing is captured if a content coding couldn't be undone, since the
        chunks are then not the representation.
        """
        if not self.content_decoded:
            return
        room = self.content_sample_size - len(self.content_sample)
        if room > 0:
            self.content_sample += chunk[:room]
            if len(chunk) > room:
                self.content_sample_truncated = True
        elif chunk:
            self.content_sample_truncated = True

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


# RFC 9112 Section 3.2.3: uri-host ":" port (rfc9112.authority_form is the older RFC 7230 rule)
AUTHORITY_FORM = rf"(?= [^:] ) {rfc3986.host} : [0-9]+"

# RFC 3987's iuserinfo: userinfo, plus non-ASCII characters
IUSERINFO = (
    rf"(?: {rfc3986.unreserved} | {rfc3986.pct_encoded} | {rfc3986.sub_delims} | : "
    r"| [^\x00-\x7f] )*"
)


def _port_invalid(port: str) -> bool:
    "True if the port isn't DIGIT+ with a value of 65535 or less."
    value = parse_digits(port, max_digits=5)
    return value is None or value > 65535


def _userinfo_valid(iri: str) -> bool:
    "True if the IRI has no userinfo, or userinfo that is valid as it stands."
    userinfo, at, _ = urlsplit(iri).netloc.rpartition("@")
    return not at or re.fullmatch(IUSERINFO, userinfo, re.VERBOSE) is not None


class HttpRequestLinter(HttpMessageLinter):
    """
    A HTTP Request message linter.
    """

    max_uri_chars = 8000
    message_type = L_("request")

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.method: Optional[str] = None
        self.iri: Optional[str] = None
        self.uri: Optional[str] = None
        # Length of the URI, before escaping ASCII in userinfo (see userinfo_escape_growth)
        self.uri_length: int = 0

    def process_request_topline(self, method: bytes, iri: bytes, version: bytes) -> None:
        self.method = method.decode("ascii", "replace")
        self.set_uri(iri.decode("utf-8", "replace"))
        self.version = version.decode("ascii", "replace")

    def set_uri(self, iri: str) -> None:
        """
        Given a unicode string (possibly an IRI), convert to a URI and make sure it's sensible.

        The request target form is checked against the method (RFC 9112 Section 3.2).
        """
        self.iri = iri
        target, has_fragment, _ = iri.partition("#")
        self.uri = target  # fallback if it can't be converted; never includes the fragment
        self.uri_length = len(target)
        if has_fragment:
            self.notes.add("uri", REQUEST_TARGET_FRAGMENT)
        if re.search(r"[\x00-\x20\x7f-\x9f]", target):
            self.notes.add("uri", URI_BAD_SYNTAX)
            return

        method = self.method or ""
        authority_form = self.method == "CONNECT"
        absolute_form = False
        if authority_form:
            pattern = AUTHORITY_FORM
        elif target == "*":
            pattern = r"\*"
        elif target.startswith("/"):
            pattern = rfc9112.origin_form
        else:
            pattern = rfc3986.absolute_URI
            absolute_form = True

        try:
            self.uri = authority_to_ascii(target) if authority_form else iri_to_uri(target)
            self.uri_length = len(self.uri) - (
                0 if authority_form else userinfo_escape_growth(target)
            )
        except (ValueError, UnicodeError):
            if authority_form:
                self.notes.add("uri", REQUEST_TARGET_FORM, method=method)
            else:
                self.notes.add("uri", URI_BAD_SYNTAX)
            return

        # Conversion encodes characters that can't be in userinfo, so check the original.
        bad_userinfo = absolute_form and not _userinfo_valid(target)
        if (
            bad_userinfo
            or not re.fullmatch(pattern, self.uri, re.VERBOSE)
            or (authority_form and _port_invalid(self.uri.rpartition(":")[2]))
        ):
            if authority_form or target == "*":
                self.notes.add("uri", REQUEST_TARGET_FORM, method=method)
            else:
                self.notes.add("uri", URI_BAD_SYNTAX)
        elif target == "*" and self.method != "OPTIONS":
            self.notes.add("uri", REQUEST_TARGET_FORM, method=method)
        if self.uri_length > self.max_uri_chars:
            self.notes.add("uri", URI_TOO_LONG, uri_len=f_num(self.uri_length))

    def can_have_content(self) -> bool:
        return True

    @property
    def response(self) -> Optional[ResponseLinterProtocol]:
        return cast(Optional[ResponseLinterProtocol], self._related)

    @response.setter
    def response(self, value: Optional[ResponseLinterProtocol]) -> None:
        self._related = value

    def post_checks(self) -> None:
        check_preflight_request(self)
        if "user-agent" not in self.headers.parsed:
            self.notes.add("field-user-agent", MISSING_USER_AGENT)

        if (
            self.content_length > 0
            and self.method
            in [
                "GET",
                "HEAD",
                "DELETE",
                "CONNECT",
                "TRACE",
            ]
            and not self.no_content
        ):
            self.notes.add("message", REQUEST_CONTENT_NOT_DEFINED, method=self.method)


class HttpResponseLinter(HttpMessageLinter):
    """
    A HTTP Response message linter.
    """

    message_type = L_("response")

    def __init__(self, **kw: Unpack[HttpMessageParams]) -> None:
        HttpMessageLinter.__init__(self, **kw)
        self.status_code_str: Optional[str] = None
        self.status_code: Optional[int] = None
        self.status_phrase: Optional[str] = None
        self.is_head_response = False
        self.caching: CachingProtocol

    @property
    def request(self) -> Optional[RequestLinterProtocol]:
        return cast(Optional[RequestLinterProtocol], self._related)

    @request.setter
    def request(self, value: Optional[RequestLinterProtocol]) -> None:
        self._related = value

    def process_response_topline(
        self, version: bytes, status_code: bytes, status_phrase: Optional[bytes] = None
    ) -> None:
        self.version = version.decode("ascii", "replace")
        self.status_code_str = status_code.decode("ascii", "replace")
        # status-code = 3DIGIT; int() would also accept "+200", " 200", "2_00" and "0200".
        if re.fullmatch(r"[0-9]{3}", self.status_code_str):
            self.status_code = int(self.status_code_str)
        else:
            self.notes.add("status", STATUS_CODE_NON_NUMERIC)
        if status_phrase:
            try:
                self.status_phrase = status_phrase.decode("ascii", "strict")
            except UnicodeDecodeError:
                self.status_phrase = status_phrase.decode("ascii", "replace")
                self.notes.add("status", STATUS_PHRASE_ENCODING)

    def can_have_content(self) -> bool:
        "Say whether this response can have content (RFC 9110, Section 6.4.1)."
        if self.is_head_response:
            return False
        if self.status_code is not None and (
            self.status_code in (204, 205, 304) or 100 <= self.status_code <= 199
        ):
            return False
        if self.is_connect_tunnel():
            return False
        return True

    def is_connect_tunnel(self) -> bool:
        """
        Say whether this is a 2xx response to CONNECT, after which the connection carries
        tunnel data rather than message content (RFC 9110, Section 9.3.6). Without a known
        request, it isn't.
        """
        return (
            self.request is not None
            and self.request.method == "CONNECT"
            and self.status_code is not None
            and 200 <= self.status_code <= 299
        )

    def has_full_representation(self) -> bool:
        "Say whether this response's content is a full representation (so, not a 206)."
        return self.can_have_content() and self.status_code != 206

    def post_checks(self) -> None:
        check_preflight_response(self)
        self.caching = ResponseCacheChecker(self)
        StatusChecker(self, self.request)
        if not self.no_content:
            verify_content_type(self)
            verify_charset(self)


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
    _summary = "The Content-Length header is incorrect."
    _text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. An incorrect `Content-Length` can cause security and interoperability
issues.

The actual content size was %(content_length)s bytes."""


class CONTENT_NOT_ALLOWED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "%(message)s can not have content."
    _text = """\
HTTP does not allow this message to have content; including it can cause security and
interoperability issues.
"""


class REQUEST_CONTENT_NOT_DEFINED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(method)s doesn't define any meaning for content."
    _text = """\
There are no defined semantics for content in `%(method)s` requests. While HTTP's framing layer
allows content to appear, that does not mean it is valid for every request method, and
including content in a `%(method)s` request can cause interoperability and security issues.
"""


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


class REQUEST_TARGET_FORM(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The request target isn't valid for %(method)s requests."
    _text = """\
`CONNECT` requests use the `host:port` authority form (no userinfo, and the port is required), `OPTIONS` requests can use `*`, and other
methods use either an absolute path (optionally with a query) or a full URI. See
[RFC 9112 Section 3.2](https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2)."""


class REQUEST_TARGET_FRAGMENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The request target contains a fragment."
    _text = """\
Fragment identifiers are handled by the client and shouldn't be sent in the request target;
recipients typically ignore or reject them. See
[RFC 9112 Section 3.2](https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2)."""


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


class MISSING_USER_AGENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The User-Agent header is missing."
    _text = """\
Clients SHOULD send a `User-Agent` header field.

See [RFC 9110 Section 10.1.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.1.5)
for details."""
