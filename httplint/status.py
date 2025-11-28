# pylint: disable=too-many-public-methods

from functools import partial
from typing import Optional, List, TYPE_CHECKING

from httplint.note import Note, levels, categories
from httplint.types import StrFieldListType

if TYPE_CHECKING:
    from httplint.message import HttpRequestLinter, HttpResponseLinter

safe_methods = [b"GET", b"HEAD", b"OPTIONS", b"TRACE"]


def get_header(hdr_tuples: StrFieldListType, name: str) -> List[str]:
    """
    Given a list of (name, value) header tuples and a header name (lowercase),
    return a list of all values for that header.

    This includes header lines with multiple values separated by a comma;
    such headers will be split into separate values. As a result, it is NOT
    safe to use this on headers whose values may include a comma (e.g.,
    Set-Cookie, or any value with a quoted string).
    """
    return [
        v.strip()
        for v in sum(
            [l.split(",") for l in [i[1] for i in hdr_tuples if i[0].lower() == name]],
            [],
        )
    ]


class StatusChecker:
    """
    Given a response, check out the status code and perform
    appropriate tests on it.

    Additional tests will be performed if the request is available.
    """

    def __init__(
        self,
        response: "HttpResponseLinter",
        request: Optional["HttpRequestLinter"] = None,
    ) -> None:
        self.request = request
        self.response = response
        self.add_note = partial(response.notes.add, status=response.status_code or 0)
        try:
            status_method = getattr(self, f"status{response.status_code}")
        except AttributeError:
            self.add_note("status", STATUS_NONSTANDARD)
            return
        status_method()

    def status100(self) -> None:  # Continue
        if self.request and not "100-continue" in get_header(
            self.request.headers.text, "expect"
        ):
            self.add_note("status", UNEXPECTED_CONTINUE)

    def status101(self) -> None:  # Switching Protocols
        if self.request and not get_header(self.request.headers.text, "upgrade"):
            self.add_note("status", UPGRADE_NOT_REQUESTED)

    def status102(self) -> None:  # Processing
        pass

    def status103(self) -> None:  # Early Hints
        self.add_note("", STATUS_EARLY_HINTS)

    def status104(self) -> None:  # Upload Resumption Supported
        self.add_note("", STATUS_UPLOAD_RESUMPTION_SUPPORTED)

    def status200(self) -> None:  # OK
        pass

    def status201(self) -> None:  # Created
        if self.request and self.request.method in safe_methods:
            self.add_note(
                "status", CREATED_SAFE_METHOD, method=self.request.method or ""
            )
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", CREATED_WITHOUT_LOCATION)

    def status202(self) -> None:  # Accepted
        pass

    def status203(self) -> None:  # Non-Authoritative Information
        pass

    def status204(self) -> None:  # No Content
        pass

    def status205(self) -> None:  # Reset Content
        pass

    def status206(self) -> None:  # Partial Content
        if self.request and not get_header(self.request.headers.text, "range"):
            self.add_note("", PARTIAL_NOT_REQUESTED)
        if "content-range" not in self.response.headers.parsed:
            self.add_note("header-location", PARTIAL_WITHOUT_RANGE)

    def status207(self) -> None:  # Multi-Status
        pass

    def status208(self) -> None:  # Already Reported
        self.add_note("", STATUS_ALREADY_REPORTED)

    def status226(self) -> None:  # IM Used
        pass

    def status300(self) -> None:  # Multiple Choices
        pass

    def status301(self) -> None:  # Moved Permanently
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status302(self) -> None:  # Found
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status303(self) -> None:  # See Other
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status304(self) -> None:  # Not Modified
        if "date" not in self.response.headers.parsed:
            self.add_note("status", NO_DATE_304)

        prohibited_headers = []
        for header in ["content-type", "content-encoding", "content-language"]:
            if header in self.response.headers.parsed:
                prohibited_headers.append(header)
        if prohibited_headers:
            self.add_note(
                "header-content-type",
                HEADER_SHOULD_NOT_BE_IN_304,
                headers="\n".join([f"* `{h}`" for h in prohibited_headers]),
            )

    def status305(self) -> None:  # Use Proxy
        self.add_note("", STATUS_DEPRECATED)

    def status306(self) -> None:  # Reserved
        self.add_note("", STATUS_RESERVED)

    def status307(self) -> None:  # Temporary Redirect
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status308(self) -> None:  # Permanent Redirect
        if "location" not in self.response.headers.parsed:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status400(self) -> None:  # Bad Request
        self.add_note("", STATUS_BAD_REQUEST)

    def status401(self) -> None:  # Unauthorized
        pass

    def status402(self) -> None:  # Payment Required
        pass

    def status403(self) -> None:  # Forbidden
        self.add_note("", STATUS_FORBIDDEN)

    def status404(self) -> None:  # Not Found
        self.add_note("", STATUS_NOT_FOUND)

    def status405(self) -> None:  # Method Not Allowed
        pass

    def status406(self) -> None:  # Not Acceptable
        self.add_note("", STATUS_NOT_ACCEPTABLE)

    def status407(self) -> None:  # Proxy Authentication Required
        pass

    def status408(self) -> None:  # Request Timeout
        pass

    def status409(self) -> None:  # Conflict
        self.add_note("", STATUS_CONFLICT)

    def status410(self) -> None:  # Gone
        self.add_note("", STATUS_GONE)

    def status411(self) -> None:  # Length Required
        pass

    def status412(self) -> None:  # Precondition Failed
        if self.request:
            match_headers = [
                "if-match",
                "if-none-match",
                "if-modified-since",
                "if-unmodified-since",
                "if-range",
            ]
            if not any(get_header(self.request.headers.text, h) for h in match_headers):
                self.add_note("", STATUS_412_WITHOUT_PRECONDITION)

    def status413(self) -> None:  # Request Entity Too Large
        self.add_note("", STATUS_REQUEST_ENTITY_TOO_LARGE)

    def status414(self) -> None:  # Request-URI Too Long
        if self.request and self.request.uri:
            uri_len = f"({len(self.request.uri)} characters)"
        else:
            uri_len = ""
        self.add_note("uri", STATUS_URI_TOO_LONG, uri_len=uri_len)

    def status415(self) -> None:  # Unsupported Media Type
        self.add_note("", STATUS_UNSUPPORTED_MEDIA_TYPE)

    def status416(self) -> None:  # Requested Range Not Satisfiable
        if self.request and not get_header(self.request.headers.text, "range"):
            self.add_note("", STATUS_416_WITHOUT_RANGE)

    def status417(self) -> None:  # Expectation Failed
        if self.request:
            expect_headers = get_header(self.request.headers.text, "expect")
            if not expect_headers:
                self.add_note("", STATUS_417_WITHOUT_EXPECT)
            elif "100-continue" in expect_headers:
                self.add_note("", STATUS_417_WITH_100_CONTINUE)

    def status418(self) -> None:
        self.add_note("", STATUS_IM_A_TEAPOT)

    def status421(self) -> None:  # Misdirected Request
        self.add_note("", STATUS_MISDIRECTED_REQUEST)

    def status422(self) -> None:  # Unprocessable Entity
        pass

    def status423(self) -> None:  # Locked
        pass

    def status424(self) -> None:  # Failed Dependency
        pass

    def status425(self) -> None:  # Too Early
        self.add_note("", STATUS_TOO_EARLY)

    def status426(self) -> None:  # Upgrade Required
        pass

    def status428(self) -> None:  # Precondition Required
        self.add_note("", STATUS_PRECONDITION_REQUIRED)

    def status429(self) -> None:  # Too Many Requests
        self.add_note("", STATUS_TOO_MANY_REQUESTS)

    def status431(self) -> None:  # Request Header Fields Too Large
        self.add_note("", STATUS_REQUEST_HEADER_FIELDS_TOO_LARGE)

    def status451(self) -> None:  # Unavailable For Legal Reasons
        self.add_note("", STATUS_UNAVAILABLE_FOR_LEGAL_REASONS)

    def status500(self) -> None:  # Internal Server Error
        self.add_note("", STATUS_INTERNAL_SERVICE_ERROR)

    def status501(self) -> None:  # Not Implemented
        self.add_note("", STATUS_NOT_IMPLEMENTED)

    def status502(self) -> None:  # Bad Gateway
        self.add_note("", STATUS_BAD_GATEWAY)

    def status503(self) -> None:  # Service Unavailable
        self.add_note("", STATUS_SERVICE_UNAVAILABLE)

    def status504(self) -> None:  # Gateway Timeout
        self.add_note("", STATUS_GATEWAY_TIMEOUT)

    def status505(self) -> None:  # HTTP Version Not Supported
        self.add_note("", STATUS_VERSION_NOT_SUPPORTED)

    def status506(self) -> None:  # Variant Also Negotiates
        pass

    def status507(self) -> None:  # Insufficient Storage
        pass

    def status508(self) -> None:  # Loop Detected
        self.add_note("", STATUS_LOOP_DETECTED)

    def status510(self) -> None:  # Not Extended
        pass

    def status511(self) -> None:  # Network Authentication Required
        self.add_note("", STATUS_NETWORK_AUTHENTICATION_REQUIRED)


class NO_DATE_304(Note):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "304 (Not Modified) responses need to have a Date header."
    _text = """\
HTTP requires `304 (Not Modified)` responses to have a `Date` header in all but the most unusual
circumstances."""


class HEADER_SHOULD_NOT_BE_IN_304(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "This 304 (Not Modified) response contains headers that should not be sent."
    )
    _text = """\
These headers are representation metadata that should not be sent in a 304 response unless
they are being used to guide cache updates:

%(headers)s

See [RFC 9110 Section 15.4.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.4.5) for
more information."""


class UNEXPECTED_CONTINUE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "A 100 (Continue) response was sent when it wasn't asked for."
    _text = """\
HTTP allows clients to ask a server if a request containing content (e.g., uploading a large file)
will succeed before sending it, using a mechanism called "Expect/continue".

When used, the client sends an `Expect: 100-continue`, in the request headers, and if the server is
willing to process it, it will send a `100 (Continue)` status code to indicate that the request
should continue.

This response has a `100 (Continue)` status code, but the request did not ask for it using the
`Expect` request header. Sending this status code without it being requested can cause
interoperability problems."""


class UPGRADE_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The protocol was upgraded without being requested."
    _text = """\
HTTP defines the `Upgrade` header as a means of negotiating a change of protocol; i.e., it
allows you to switch the protocol on a given connection from HTTP to something else.

This response was upgraded, but the request did not contain an `Upgrade` header field.
"""


class CREATED_SAFE_METHOD(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "A new resource was created in response to a safe request."
    _text = """\
The `201 (Created)` status code indicates that the request created a new resource.

However, the request method used (%(method)s) is defined as a "safe" method; that is, it
should not have any side effects.

Creating resources as a side effect of a safe method can have unintended consequences; for example,
search engine spiders and similar automated agents often follow links, and intermediaries sometimes
re-try safe methods when they fail."""


class CREATED_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "A new resource was created without its location being sent."
    _text = """\
The `201 (Created)` status code indicates that the request created a new resource.

HTTP specifies that the URL of the new resource is to be indicated in the `Location` header,
but it isn't present in this response."""


class PARTIAL_WITHOUT_RANGE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "This response is partial, but doesn't have a Content-Range header."
    _text = """\
The `206 (Partial Response)` status code indicates that the response content is only partial.

However, for a response to be partial, it needs to have a `Content-Range` header to indicate
what part of the full response it carries. This response does not have one."""


class PARTIAL_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "A partial response was sent when it wasn't requested."
    _text = """\
The `206 (Partial Response)` status code indicates that the response content is only partial.

However, the client needs to ask for it with the `Range` header, and the request did not
include one."""


class REDIRECT_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Redirects need to have a Location header."
    _text = """\
The %(status)s status code redirects users to another URI. The `Location` header is used to
convey this URI, but a valid one isn't present in this response."""


class STATUS_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(status)s status code is deprecated."
    _text = """\
When a status code is deprecated, it should not be used, because its meaning is not well-defined
enough to ensure interoperability."""


class STATUS_RESERVED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(status)s status code is reserved."
    _text = """\
Reserved status codes can only be used by future, standard protocol extensions; they are not for
private use."""


class STATUS_NONSTANDARD(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "%(status)s is not a standard HTTP status code."
    _text = """\
Non-standard status codes are not well-defined and interoperable. Instead of defining your own
status code, you should reuse one of the more generic ones; for example, `400` for a client-side
problem, or `500` for a server-side problem."""


class STATUS_BAD_REQUEST(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The server didn't understand the request."
    _text = """\
"""


class STATUS_FORBIDDEN(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server has forbidden this request."
    _text = """\
"""


class STATUS_NOT_FOUND(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource could not be found."
    _text = """\
The server couldn't find any resource to serve for the given URI."""


class STATUS_NOT_ACCEPTABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource could not be found."
    _text = """\
"""


class STATUS_CONFLICT(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The request conflicted with the state of the resource."
    _text = """\
"""


class STATUS_GONE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource is gone."
    _text = """\
The server previously had a resource at the given URI, but it is no longer there."""


class STATUS_REQUEST_ENTITY_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The request content was too large for the server."
    _text = """\
The server rejected the request because the request content sent was too large."""


class STATUS_URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The server won't accept a URI this long %(uri_len)s."
    _text = """\
The %(status)s status code means that the server can't or won't accept a request-uri this long."""


class STATUS_UNSUPPORTED_MEDIA_TYPE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource doesn't support this media type in requests."
    _text = """\
"""


class STATUS_IM_A_TEAPOT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "The server returned 418 (I'm a Teapot), an easter egg defined in RFC 2324."
    )
    _text = """\
RFC 2324 was an April Fools' Day RFC that lampooned the various ways HTTP was abused; one such abuse
was the definition of the application-specific `418 (I'm a Teapot)` status code. In the
intervening years, this status code has been sometimes implemented as an "easter egg".

This status code is not a part of HTTP and hence it might not be supported by some strict
standards-compliant clients.
"""


class STATUS_INTERNAL_SERVICE_ERROR(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "There was a general server error."
    _text = """\
"""


class STATUS_NOT_IMPLEMENTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server doesn't implement the request method."
    _text = """\
"""


class STATUS_BAD_GATEWAY(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "An intermediary encountered an error."
    _text = """\
"""


class STATUS_SERVICE_UNAVAILABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server is temporarily unavailable."
    _text = """\
"""


class STATUS_GATEWAY_TIMEOUT(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "An intermediary timed out."
    _text = """\
"""


class STATUS_VERSION_NOT_SUPPORTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The request HTTP version isn't supported."
    _text = """\
"""


class STATUS_412_WITHOUT_PRECONDITION(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The request didn't have any preconditions."
    _text = """\
The `412 (Precondition Failed)` status code indicates that one or more conditions given in the
request header fields evaluated to false when tested on the server.

However, this request didn't contain any conditional headers (such as `If-Match`, `If-None-Match`,
`If-Modified-Since`, `If-Unmodified-Since`, or `If-Range`)."""


class STATUS_416_WITHOUT_RANGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The request didn't have a Range header."
    _text = """\
The `416 (Range Not Satisfiable)` status code indicates that the set of ranges in the request's
`Range` header field overlap the current extent of the selected resource.

However, this request didn't contain a `Range` header."""


class STATUS_417_WITHOUT_EXPECT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The request didn't have an Expect header."
    _text = """\
The `417 (Expectation Failed)` status code indicates that the expectation given in the request's
`Expect` header field could not be met by at least one of the inbound servers.

However, this request didn't contain an `Expect` header."""


class STATUS_417_WITH_100_CONTINUE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server couldn't meet the 100-continue expectation."
    _text = """\
The `417 (Expectation Failed)` status code indicates that the expectation given in the request's
`Expect` header field could not be met by at least one of the inbound servers.

In this case, the client requested `100-continue`, but the server (or an intermediary) couldn't
satisfy it."""


class STATUS_EARLY_HINTS(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server sent early hints."
    _text = """\
The `103 (Early Hints)` status code allows the server to send some headers before the final response,
typically to help the client start fetching resources earlier."""


class STATUS_UPLOAD_RESUMPTION_SUPPORTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server supports upload resumption."
    _text = """\
The `104 (Upload Resumption Supported)` status code indicates that the server supports resumable
uploads."""


class STATUS_ALREADY_REPORTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The members of a DAV binding have already been enumerated."
    _text = """\
The `208 (Already Reported)` status code can be used inside a DAV: propstat response element to
avoid enumerating the internal members of multiple bindings to the same collection repeatedly."""


class STATUS_MISDIRECTED_REQUEST(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = (
        "The request was directed at a server that is not able to produce a response."
    )
    _text = """\
The `421 (Misdirected Request)` status code indicates that the request was directed at a server
that is not able to produce a response. This can happen when a connection is reused."""


class STATUS_TOO_EARLY(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = (
        "The server is unwilling to risk processing a request that might be replayed."
    )
    _text = """\
The `425 (Too Early)` status code indicates that the server is unwilling to risk processing a
request that might be replayed."""


class STATUS_PRECONDITION_REQUIRED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The origin server requires the request to be conditional."
    _text = """\
The `428 (Precondition Required)` status code indicates that the origin server requires the request
to be conditional."""


class STATUS_TOO_MANY_REQUESTS(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The client has sent too many requests in a given amount of time."
    _text = """\
The `429 (Too Many Requests)` status code indicates that the client has sent too many requests in a
given amount of time ("rate limiting")."""


class STATUS_REQUEST_HEADER_FIELDS_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The server is unwilling to process the request because its headers are too large."
    _text = """\
The `431 (Request Header Fields Too Large)` status code indicates that the server is unwilling to
process the request because its header fields are too large."""


class STATUS_UNAVAILABLE_FOR_LEGAL_REASONS(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The resource is unavailable for legal reasons."
    _text = """\
The `451 (Unavailable For Legal Reasons)` status code indicates that the server is denying access to
the resource as a consequence of a legal demand."""


class STATUS_LOOP_DETECTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = (
        "The server terminated an operation because it encountered an infinite loop."
    )
    _text = """\
The `508 (Loop Detected)` status code indicates that the server terminated an operation because it
encountered an infinite loop while processing a request with "Depth: infinity"."""


class STATUS_NETWORK_AUTHENTICATION_REQUIRED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The client needs to authenticate to gain network access."
    _text = """\
The `511 (Network Authentication Required)` status code indicates that the client needs to
authenticate to gain network access."""
