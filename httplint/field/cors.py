from typing import cast, TYPE_CHECKING

from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter, HttpRequestLinter


def check_preflight_request_header(
    message: "HttpMessageLinter", canonical_name: str, add_note: AddNoteMethodType
) -> None:
    """
    Check if the header is only present in a message that is a CORS preflight request.
    """
    # pylint: disable=import-outside-toplevel
    from httplint.message import HttpRequestLinter

    if isinstance(message, HttpRequestLinter):
        if message.method != "OPTIONS":
            add_note(
                CORS_PREFLIGHT_REQ_METHOD_WRONG,
                field_name=canonical_name,
                method=message.method,
            )
        if "origin" not in message.headers.parsed:
            add_note(CORS_PREFLIGHT_REQ_NO_ORIGIN, field_name=canonical_name)
        if (
            canonical_name == "Access-Control-Request-Headers"
            and "access-control-request-method" not in message.headers.parsed
        ):
            add_note(CORS_PREFLIGHT_REQ_NO_METHOD, field_name=canonical_name)


def check_preflight_response(
    message: "HttpMessageLinter", canonical_name: str, add_note: AddNoteMethodType
) -> None:
    """
    Check if the header is only present in a CORS preflight response.
    """
    if message.related:
        request = cast("HttpRequestLinter", message.related)
        request_headers = {n.lower() for n, v in request.headers.text}
        is_preflight = (
            request.method == "OPTIONS"
            and "origin" in request_headers
            and "access-control-request-method" in request_headers
        )
        if not is_preflight:
            add_note(CORS_PREFLIGHT_ONLY, field_name=canonical_name)


class CORS_PREFLIGHT_ONLY(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The %(field_name)s header is only allowed in CORS preflight responses."
    _text = """\
The `%(field_name)s` header is only used in the response to a Cross-Origin Resource Sharing (CORS)
preflight request.

A preflight request is an `OPTIONS` request that includes an `Origin` header and an
`Access-Control-Request-Method` header.

This response was not to a CORS preflight request, so this header should not be present."""


class CORS_PREFLIGHT_REQ_METHOD_WRONG(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The %(field_name)s header is only allowed in CORS preflight requests."
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request uses the `OPTIONS` method; this request uses `%(method)s`."""


class CORS_PREFLIGHT_REQ_NO_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The %(field_name)s header requires the Origin header."
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request requires the `Origin` header to be present."""


class CORS_PREFLIGHT_REQ_NO_METHOD(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = (
        "The %(field_name)s header requires the Access-Control-Request-Method header."
    )
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request requires the `Access-Control-Request-Method` header to be present."""
