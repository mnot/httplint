from typing import cast, TYPE_CHECKING

from httplint.note import Note, categories, levels

if TYPE_CHECKING:
    from httplint.message import HttpResponseLinter, HttpRequestLinter


def is_cors_preflight_request(message: "HttpRequestLinter") -> bool:
    """
    Check if the message is a CORS preflight request.
    """
    return (
        message.method == "OPTIONS"
        and "origin" in message.headers.parsed
        and "access-control-request-method" in message.headers.parsed
    )


def check_preflight_request(message: "HttpRequestLinter") -> None:
    """
    Check if the message is a CORS preflight request.
    """
    if is_cors_preflight_request(message):
        message.notes.add(
            "method field-access-control-request-method field-access-control-request-headers",
            CORS_PREFLIGHT_REQUEST,
        )

    has_acr_method = "access-control-request-method" in message.headers.parsed
    has_acr_headers = "access-control-request-headers" in message.headers.parsed

    if has_acr_method or has_acr_headers:
        if message.method != "OPTIONS":
            message.notes.add(
                "method",
                CORS_PREFLIGHT_REQ_METHOD_WRONG,
                field_name="Access-Control-Request-Method",
                method=message.method,
            )
        if "origin" not in message.headers.parsed:
            message.notes.add(
                "field-origin",
                CORS_PREFLIGHT_REQ_NO_ORIGIN,
                field_name="Access-Control-Request-Method",
            )
        if not has_acr_method:
            message.notes.add(
                "field-access-control-request-headers",
                CORS_PREFLIGHT_REQ_NO_METHOD,
                field_name="Access-Control-Request-Headers",
            )


def check_preflight_response(message: "HttpResponseLinter") -> None:
    """
    Check if the message is a CORS preflight response.
    """
    is_preflight = False
    if message.related:
        request = cast("HttpRequestLinter", message.related)
        is_preflight = is_cors_preflight_request(request)

    if is_preflight:
        message.notes.add("", CORS_PREFLIGHT_RESPONSE)
    else:
        # Check for CORS headers in non-preflight response
        bad_headers = []
        for field_name in [
            "access-control-allow-headers",
            "access-control-allow-methods",
            "access-control-max-age",
        ]:
            if field_name in message.headers.parsed:
                bad_headers.append(message.headers.handlers[field_name].canonical_name)

        if bad_headers:
            message.notes.add(
                "header-access-control-allow-headers",
                CORS_PREFLIGHT_ONLY,
                headers=", ".join(bad_headers),
            )

    # Check for Access-Control-Allow-Origin semantics
    if "access-control-allow-origin" in message.headers.parsed:
        acao_value = message.headers.parsed["access-control-allow-origin"]
        if isinstance(acao_value, str):
            if " " in acao_value or "," in acao_value:
                message.notes.add("header-access-control-allow-origin", ACAO_MULTIPLE_VALUES)


class CORS_PREFLIGHT_REQUEST(Note):
    category = categories.CORS
    level = levels.INFO
    _summary = "This is a CORS preflight request."
    _text = """\
This is a Cross-Origin Resource Sharing (CORS) preflight request.

A preflight request uses the `OPTIONS` method and includes an `Origin` and `Access-Control-Request-Method`
header."""


class CORS_PREFLIGHT_REQ_METHOD_WRONG(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "The %(field_name)s header requires the OPTIONS method."
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request uses the `OPTIONS` method; this request uses `%(method)s`."""


class CORS_PREFLIGHT_REQ_NO_ORIGIN(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "The %(field_name)s header requires the Origin header."
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request requires the `Origin` header to be present."""


class CORS_PREFLIGHT_REQ_NO_METHOD(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "The %(field_name)s header requires the Access-Control-Request-Method header."
    _text = """\
The `%(field_name)s` header is only used in a Cross-Origin Resource Sharing (CORS) preflight
request.

A preflight request requires the `Access-Control-Request-Method` header to be present."""


class CORS_PREFLIGHT_RESPONSE(Note):
    category = categories.CORS
    level = levels.INFO
    _summary = "This is a CORS preflight response."
    _text = """\
This is a Cross-Origin Resource Sharing (CORS) preflight response.

It is a response to an `OPTIONS` request that includes an `Origin` and `Access-Control-Request-Method`
header."""


class CORS_PREFLIGHT_ONLY(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "CORS headers are only allowed in preflight responses."
    _text = """\
The following header(s) are only used in the response to a Cross-Origin Resource Sharing (CORS)
preflight request:

%(headers)s

A preflight request is an `OPTIONS` request that includes an `Origin` header and an
`Access-Control-Request-Method` header.

This response was not to a CORS preflight request, so these headers should not be present."""


class ACAO_MULTIPLE_VALUES(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "Access-Control-Allow-Origin should not have multiple values."
    _text = """\
The `Access-Control-Allow-Origin` header can only contain a single origin, `*`, or `null`. It
cannot contain a list of origins."""


class ACAC_NOT_TRUE(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "Access-Control-Allow-Credentials must be 'true'."
    _text = """\
The `Access-Control-Allow-Credentials` header must be set to `true` if present. If you don't want
to allow credentials, omit the header."""
