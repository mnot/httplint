# pylint: disable=duplicate-code
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from http_sf import Token

from httplint.field.sf_helpers import check_sf_params
from httplint.field.sf_member import is_string_or_token, member_text, member_type_phrase
from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFListType,
)
from httplint.util import inline_safe


class proxy_status(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Proxy-Status"
    description = """\
The `Proxy-Status` header field indicates how intermediaries have handled the response."""
    reference = "https://www.rfc-editor.org/rfc/rfc9209.html#section-2"
    syntax = False  # Structured Field
    deprecated = False
    sf_type = "list"
    value: SFListType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        status_list = []
        for target, params in self.value:
            if not is_string_or_token(target):
                add_note(
                    PROXY_STATUS_BAD_MEMBER,
                    member_type=member_type_phrase(target),
                    # An empty value would leave an empty code span in the note text.
                    value=member_text(target) or MarkdownSafe("(empty)"),
                )
            target_str = inline_safe(member_text(target))
            param_str = check_sf_params(
                params,
                KNOWN_PARAMS,
                add_note,
                PROXY_STATUS_UNKNOWN_PARAM,
                PROXY_STATUS_BAD_PARAM_VAL,
            )
            # An empty code span would swallow the next span's delimiters.
            label = f"**`{target_str}`**" if target_str else "**(empty)**"
            status_list.append(f"{label}:\n\n{param_str}")

        if status_list:
            add_note(PROXY_STATUS, status=MarkdownSafe("\n\n".join(status_list)))


KNOWN_PARAMS: Dict[str, Dict[str, Any]] = {
    "error": {
        "type": Token,
        "value_desc": {
            Token(
                "dns_timeout"
            ): "The proxy encountered a timeout when trying to resolve the hostname.",
            Token("dns_error"): "The proxy encountered a DNS error.",
            Token(
                "destination_not_found"
            ): "The proxy could not determine the IP address of the next hop.",
            Token("destination_unavailable"): "The proxy could not connect to the next hop.",
            Token(
                "destination_ip_prohibited"
            ): "The proxy was configured to block access to the next hop IP.",
            Token(
                "destination_ip_unroutable"
            ): "The proxy could not route packets to the next hop IP.",
            Token("connection_refused"): "The proxy's connection to the next hop was refused.",
            Token("connection_terminated"): "The proxy's connection to the next hop was closed.",
            Token("connection_timeout"): "The proxy's connection to the next hop timed out.",
            Token(
                "connection_read_timeout"
            ): "The proxy encountered a timeout while waiting for data.",
            Token(
                "connection_write_timeout"
            ): "The proxy encountered a timeout while writing data.",
            Token("connection_limit_reached"): "The proxy reached a limit on open connections.",
            Token("tls_protocol_error"): "The proxy encountered a TLS error.",
            Token("tls_certificate_error"): "The proxy encountered a certificate error.",
            Token("tls_alert_received"): "The proxy received a TLS alert.",
            Token(
                "http_request_error"
            ): "The proxy encountered an error while generating the request.",
            Token("http_request_denied"): "The proxy denied the request.",
            Token("http_response_incomplete"): "The proxy received an incomplete response.",
            Token(
                "http_response_header_section_size"
            ): "The proxy received a header section that was too large.",
            Token("http_response_header_size"): "The proxy received a header that was too large.",
            Token("http_response_body_size"): "The proxy received a body that was too large.",
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
            Token("proxy_configuration_error"): "The proxy encountered a configuration error.",
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


class PROXY_STATUS_BAD_MEMBER(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "A Proxy-Status member is %(member_type)s, not a String or Token."
    _text = """\
Each member of the `Proxy-Status` list identifies the intermediary that inserted it, and
[RFC 9209](https://www.rfc-editor.org/rfc/rfc9209.html#section-2) requires it to be a String or
a Token. This member, `%(value)s`, is %(member_type)s."""


class PROXY_STATUS_UNKNOWN_PARAM(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "The Proxy-Status header has an unknown parameter '%(param)s'."
    _text = """\
The `%(param)s` parameter is not defined in the Proxy-Status specification.
"""


class PROXY_STATUS_BAD_PARAM_VAL(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The Proxy-Status header has an unknown value for '%(param)s'."
    _text = """\
The value `%(value)s` is not defined for the `%(param)s` parameter.
"""


class ProxyStatusTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [
        b"ExampleProxy; error=http_protocol_error",
        b"AnotherProxy; next-hop=example.com",
    ]
    expected_out = [
        (Token("ExampleProxy"), {"error": Token("http_protocol_error")}),
        (Token("AnotherProxy"), {"next-hop": "example.com"}),
    ]
    expected_notes: NoteClassListType = [PROXY_STATUS]


class ProxyStatusUnknownParamTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"ExampleProxy; unknown=1"]
    expected_out = [(Token("ExampleProxy"), {"unknown": 1})]
    expected_notes: NoteClassListType = [PROXY_STATUS_UNKNOWN_PARAM, PROXY_STATUS]


class ProxyStatusBadParamValTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b'ExampleProxy; error="string"']
    expected_out = [(Token("ExampleProxy"), {"error": "string"})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_PARAM_VAL, PROXY_STATUS]


class ProxyStatusBooleanIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"ExampleProxy; received-status=?1"]
    expected_out = [(Token("ExampleProxy"), {"received-status": True})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_PARAM_VAL, PROXY_STATUS]


class ProxyStatusBadMemberInnerListTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"(a b)"]
    expected_out = [([(Token("a"), {}), (Token("b"), {})], {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"1"]
    expected_out = [(1, {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberDecimalTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"1.5"]
    expected_out = [(Decimal("1.5"), {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberBooleanTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"?1"]
    expected_out = [(True, {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberByteSequenceTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b":YWJj:"]
    expected_out = [(b"abc", {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberAmongGoodTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b'a, 1, "b"; next-protocol=h2, (c d)']
    expected_out = [
        (Token("a"), {}),
        (1, {}),
        ("b", {"next-protocol": Token("h2")}),
        ([(Token("c"), {}), (Token("d"), {})], {}),
    ]
    expected_notes: NoteClassListType = [
        PROXY_STATUS_BAD_MEMBER,
        PROXY_STATUS_BAD_MEMBER,
        PROXY_STATUS,
    ]


class ProxyStatusStringAndTokenMembersTest(FieldTest[ResponseLinterProtocol]):
    "Guard: String and Token members get no member-type note."

    name = "Proxy-Status"
    inputs = [b'a, "b c"']
    expected_out = [(Token("a"), {}), ("b c", {})]
    expected_notes: NoteClassListType = [PROXY_STATUS]


class ProxyStatusBadMemberDateTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"@1659578233"]
    expected_out = [(datetime.fromtimestamp(1659578233, tz=timezone.utc), {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberEmptyByteSequenceTest(FieldTest[ResponseLinterProtocol]):
    name = "Proxy-Status"
    inputs = [b"::"]
    expected_out = [(b"", {})]
    expected_notes: NoteClassListType = [PROXY_STATUS_BAD_MEMBER, PROXY_STATUS]


class ProxyStatusBadMemberWithParamsTest(FieldTest[ResponseLinterProtocol]):
    "The parameters of a bad member are still checked."

    name = "Proxy-Status"
    inputs = [b"1; next-protocol=1"]
    expected_out = [(1, {"next-protocol": 1})]
    expected_notes: NoteClassListType = [
        PROXY_STATUS_BAD_MEMBER,
        PROXY_STATUS_BAD_PARAM_VAL,
        PROXY_STATUS,
    ]
