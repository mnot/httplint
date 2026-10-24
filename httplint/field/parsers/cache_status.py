# pylint: disable=duplicate-code
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from http_sf import Token

from httplint.field.sf_member import is_string_or_token, member_text, member_type_phrase
from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.field.utils import check_sf_params
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
    SFListType,
)
from httplint.util import inline_safe


class cache_status(StructuredField[ResponseLinterProtocol]):
    canonical_name = "Cache-Status"
    description = """\
The `Cache-Status` header field indicates how caches have handled the response, to help with
debugging caches."""
    reference = "https://www.rfc-editor.org/rfc/rfc9211.html#section-2"
    syntax = False  # Structured Field
    category = categories.CACHING
    deprecated = False
    sf_type = "list"
    value: SFListType

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        status_list = []
        for target, params in self.value:
            if not is_string_or_token(target):
                add_note(
                    CACHE_STATUS_BAD_MEMBER,
                    member_type=member_type_phrase(target),
                    # An empty value would leave an empty code span in the note text.
                    value=member_text(target) or MarkdownSafe("(empty)"),
                )
            target_str = inline_safe(member_text(target))
            param_str = check_sf_params(
                params,
                KNOWN_PARAMS,
                add_note,
                CACHE_STATUS_UNKNOWN_PARAM,
                CACHE_STATUS_BAD_PARAM_VAL,
            )
            # An empty code span would swallow the next span's delimiters.
            label = f"**`{target_str}`**" if target_str else "**(empty)**"
            status_list.append(f"{label}:\n\n{param_str}")

        if status_list:
            add_note(CACHE_STATUS, status=MarkdownSafe("\n\n".join(status_list)))


KNOWN_PARAMS: Dict[str, Dict[str, Any]] = {
    "hit": {"type": bool, "desc": "The response was served from the cache."},
    "fwd": {
        "type": Token,
        "values": [
            Token("bypass"),
            Token("method"),
            Token("uri-miss"),
            Token("vary-miss"),
            Token("miss"),
            Token("request"),
            Token("stale"),
            Token("partial"),
        ],
        "value_desc": {
            Token("bypass"): "The cache was configured to bypass the cache.",
            Token("method"): "The request method's semantics require the request to be forwarded.",
            Token("uri-miss"): "The cache did not contain a response for the URI.",
            Token(
                "vary-miss"
            ): "The cache contained a response for the URI, but it could not be selected.",
            Token("miss"): "The cache did not contain a response.",
            Token("request"): "The cache was requested to forward the request.",
            Token("stale"): "The cache contained a stale response.",
            Token("partial"): "The cache contained a partial response.",
        },
    },
    "fwd-status": {
        "type": int,
        "desc": "The status code of the forwarded request was %s.",
    },
    "ttl": {
        "type": int,
        "desc": "The response's remaining time-to-live was %s seconds.",
    },
    "stored": {"type": bool, "desc": "The response was stored in the cache."},
    "collapsed": {
        "type": bool,
        "desc": "The request was collapsed with another request.",
    },
    "key": {"type": str, "desc": "The cache key was `%s`."},
    "detail": {"type": (Token, str), "desc": "Additional details: %s"},
}


class CACHE_STATUS(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "Detailed information about caching is available."
    _text = """\
The `Cache-Status` header field indicates how caches have handled the response.

%(status)s
"""


class CACHE_STATUS_BAD_MEMBER(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "A Cache-Status member is %(member_type)s, not a String or Token."
    _text = """\
Each member of the `Cache-Status` list identifies the cache that inserted it, and
[RFC 9211](https://www.rfc-editor.org/rfc/rfc9211.html#section-2) requires it to be a String or
a Token. This member, `%(value)s`, is %(member_type)s."""


class CACHE_STATUS_UNKNOWN_PARAM(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "The Cache-Status header has an unknown parameter '%(param)s'."
    _text = """\
The `%(param)s` parameter is not defined in the Cache-Status specification.
"""


class CACHE_STATUS_BAD_PARAM_VAL(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The Cache-Status header has an unknown value for '%(param)s'."
    _text = """\
The value `%(value)s` is not defined for the `%(param)s` parameter.
"""


class CacheStatusTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"ExampleCache; hit; ttl=3700", b"AnotherCache; fwd=uri-miss"]
    expected_out = [
        (Token("ExampleCache"), {"hit": True, "ttl": 3700}),
        (Token("AnotherCache"), {"fwd": Token("uri-miss")}),
    ]
    expected_notes: NoteClassListType = [CACHE_STATUS]


class CacheStatusUnknownParamTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"ExampleCache; unknown=1"]
    expected_out = [(Token("ExampleCache"), {"unknown": 1})]
    expected_notes: NoteClassListType = [CACHE_STATUS_UNKNOWN_PARAM, CACHE_STATUS]


class CacheStatusBadParamValTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"ExampleCache; fwd=invalid"]
    expected_out = [(Token("ExampleCache"), {"fwd": Token("invalid")})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_PARAM_VAL, CACHE_STATUS]


class CacheStatusBooleanIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"ExampleCache; fwd-status=?1; ttl=?1"]
    expected_out = [(Token("ExampleCache"), {"fwd-status": True, "ttl": True})]
    expected_notes: NoteClassListType = [
        CACHE_STATUS_BAD_PARAM_VAL,
        CACHE_STATUS_BAD_PARAM_VAL,
        CACHE_STATUS,
    ]


class CacheStatusEmptyTargetTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b'""; hit; key=""']
    expected_out = [("", {"hit": True, "key": ""})]
    expected_notes: NoteClassListType = [CACHE_STATUS]


class CacheStatusEmptyParamValTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b'ExampleCache; fwd=""']
    expected_out = [(Token("ExampleCache"), {"fwd": ""})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_PARAM_VAL, CACHE_STATUS]


class CacheStatusBadMemberInnerListTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"(a b)"]
    expected_out = [([(Token("a"), {}), (Token("b"), {})], {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberIntegerTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"1"]
    expected_out = [(1, {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberDecimalTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"1.5"]
    expected_out = [(Decimal("1.5"), {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberBooleanTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"?1"]
    expected_out = [(True, {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberByteSequenceTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b":YWJj:"]
    expected_out = [(b"abc", {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberAmongGoodTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b'a, 1, "b"; hit, (c d)']
    expected_out = [
        (Token("a"), {}),
        (1, {}),
        ("b", {"hit": True}),
        ([(Token("c"), {}), (Token("d"), {})], {}),
    ]
    expected_notes: NoteClassListType = [
        CACHE_STATUS_BAD_MEMBER,
        CACHE_STATUS_BAD_MEMBER,
        CACHE_STATUS,
    ]


class CacheStatusStringAndTokenMembersTest(FieldTest[ResponseLinterProtocol]):
    "Guard: String and Token members get no member-type note."

    name = "Cache-Status"
    inputs = [b'a, "b c"']
    expected_out = [(Token("a"), {}), ("b c", {})]
    expected_notes: NoteClassListType = [CACHE_STATUS]


class CacheStatusBadMemberDateTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"@1659578233"]
    expected_out = [(datetime.fromtimestamp(1659578233, tz=timezone.utc), {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberEmptyByteSequenceTest(FieldTest[ResponseLinterProtocol]):
    name = "Cache-Status"
    inputs = [b"::"]
    expected_out = [(b"", {})]
    expected_notes: NoteClassListType = [CACHE_STATUS_BAD_MEMBER, CACHE_STATUS]


class CacheStatusBadMemberWithParamsTest(FieldTest[ResponseLinterProtocol]):
    "The parameters of a bad member are still checked."

    name = "Cache-Status"
    inputs = [b"1; hit=5"]
    expected_out = [(1, {"hit": 5})]
    expected_notes: NoteClassListType = [
        CACHE_STATUS_BAD_MEMBER,
        CACHE_STATUS_BAD_PARAM_VAL,
        CACHE_STATUS,
    ]
