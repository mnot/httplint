from typing import Any, Dict
from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.field.utils import check_sf_params
from httplint.types import AddNoteMethodType


class proxy_status(HttpField):
    canonical_name = "Proxy-Status"
    description = """\
The `Proxy-Status` header field indicates how intermediaries have handled the response."""
    reference = "https://www.rfc-editor.org/rfc/rfc9209.html#section-2"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True
    structured_field = True
    sf_type = "list"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        status_list = []
        bad_structure = False
        for member in self.value:
            if isinstance(member, tuple):
                target = member[0]
                params = member[1]
            else:
                bad_structure = True
                continue

            param_str = check_sf_params(
                params,
                KNOWN_PARAMS,
                add_note,
                PROXY_STATUS_UNKNOWN_PARAM,
                PROXY_STATUS_BAD_PARAM_VAL,
            )
            status_list.append(f"**{target}**:\n{param_str}")

        if status_list:
            add_note(PROXY_STATUS, status="\n\n".join(status_list))

        if bad_structure:
            add_note(PROXY_STATUS_BAD_STRUCTURE)


KNOWN_PARAMS: Dict[str, Dict[str, Any]] = {
    "error": {
        "type": Token,
        "desc": "The error was `%s`.",
        "value_desc": {
            Token(
                "dns_timeout"
            ): "The proxy encountered a timeout when trying to resolve the hostname.",
            Token("dns_error"): "The proxy encountered a DNS error.",
            Token(
                "destination_not_found"
            ): "The proxy could not determine the IP address of the next hop.",
            Token(
                "destination_unavailable"
            ): "The proxy could not connect to the next hop.",
            Token(
                "destination_ip_prohibited"
            ): "The proxy was configured to block access to the next hop IP.",
            Token(
                "destination_ip_unroutable"
            ): "The proxy could not route packets to the next hop IP.",
            Token(
                "connection_refused"
            ): "The proxy's connection to the next hop was refused.",
            Token(
                "connection_terminated"
            ): "The proxy's connection to the next hop was closed.",
            Token(
                "connection_timeout"
            ): "The proxy's connection to the next hop timed out.",
            Token(
                "connection_read_timeout"
            ): "The proxy encountered a timeout while waiting for data.",
            Token(
                "connection_write_timeout"
            ): "The proxy encountered a timeout while writing data.",
            Token(
                "connection_limit_reached"
            ): "The proxy reached a limit on open connections.",
            Token("tls_protocol_error"): "The proxy encountered a TLS error.",
            Token(
                "tls_certificate_error"
            ): "The proxy encountered a certificate error.",
            Token("tls_alert_received"): "The proxy received a TLS alert.",
            Token(
                "http_request_error"
            ): "The proxy encountered an error while generating the request.",
            Token("http_request_denied"): "The proxy denied the request.",
            Token(
                "http_response_incomplete"
            ): "The proxy received an incomplete response.",
            Token(
                "http_response_header_section_size"
            ): "The proxy received a header section that was too large.",
            Token(
                "http_response_header_size"
            ): "The proxy received a header that was too large.",
            Token(
                "http_response_body_size"
            ): "The proxy received a body that was too large.",
            Token(
                "http_response_transfer_coding"
            ): "The proxy encountered an error decoding the transfer coding.",
            Token(
                "http_response_content_coding"
            ): "The proxy encountered an error decoding the content coding.",
            Token(
                "http_response_timeout"
            ): "The proxy encountered a timeout while waiting for the response.",
            Token("http_upgrade_failed"): "The proxy failed to upgrade the connection.",
            Token("http_protocol_error"): "The proxy encountered a protocol error.",
            Token("proxy_internal_error"): "The proxy encountered an internal error.",
            Token(
                "proxy_configuration_error"
            ): "The proxy encountered a configuration error.",
            Token("proxy_loop_detected"): "The proxy detected a loop.",
        },
    },
    "next-hop": {"type": (Token, str), "desc": "The next hop was `%s`."},
    "next-protocol": {"type": Token, "desc": "The next protocol was `%s`."},
    "received-status": {"type": int, "desc": "The received status code was %s."},
    "details": {"type": (Token, str), "desc": "Additional details: %s"},
}


class PROXY_STATUS(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "Information about intermediaries is available."
    _text = """\
The `Proxy-Status` header field indicates how intermediaries have handled the response.

%(status)s
"""


class PROXY_STATUS_BAD_STRUCTURE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "%(message)s has a Proxy-Status header with an invalid structure."
    _text = """\
The `Proxy-Status` header must be a list of members, where each member is
a Token or String (identifying the proxy) with optional parameters.
"""


class PROXY_STATUS_UNKNOWN_PARAM(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = (
        "%(message)s has a Proxy-Status header with an unknown parameter '%(param)s'."
    )
    _text = """\
The `%(param)s` parameter is not defined in the Proxy-Status specification.
"""


class PROXY_STATUS_BAD_PARAM_VAL(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = (
        "%(message)s has a Proxy-Status header with an unknown value for '%(param)s'."
    )
    _text = """\
The value `%(value)s` is not defined for the `%(param)s` parameter.
"""


class ProxyStatusTest(FieldTest):
    name = "Proxy-Status"
    inputs = [
        b"ExampleProxy; error=http_protocol_error",
        b"AnotherProxy; next-hop=example.com",
    ]
    expected_out = [
        (Token("ExampleProxy"), {"error": Token("http_protocol_error")}),
        (Token("AnotherProxy"), {"next-hop": "example.com"}),
    ]
    expected_notes = [PROXY_STATUS]


class ProxyStatusUnknownParamTest(FieldTest):
    name = "Proxy-Status"
    inputs = [b"ExampleProxy; unknown=1"]
    expected_out = [(Token("ExampleProxy"), {"unknown": 1})]
    expected_notes = [PROXY_STATUS_UNKNOWN_PARAM, PROXY_STATUS]


class ProxyStatusBadParamValTest(FieldTest):
    name = "Proxy-Status"
    inputs = [b'ExampleProxy; error="string"']
    expected_out = [(Token("ExampleProxy"), {"error": "string"})]
    expected_notes = [PROXY_STATUS_BAD_PARAM_VAL, PROXY_STATUS]
