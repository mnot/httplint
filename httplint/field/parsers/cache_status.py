from typing import Any, Dict
from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.field.utils import check_sf_params
from httplint.types import AddNoteMethodType


class cache_status(HttpField):
    canonical_name = "Cache-Status"
    description = """\
The `Cache-Status` header field indicates how caches have handled the response, to help with
debugging caches."""
    reference = "https://www.rfc-editor.org/rfc/rfc9211.html#section-2"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = False
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
                CACHE_STATUS_UNKNOWN_PARAM,
                CACHE_STATUS_BAD_PARAM_VAL,
            )
            status_list.append(f"**{target}**:\n{param_str}")

        if status_list:
            add_note(CACHE_STATUS, status="\n\n".join(status_list))

        if bad_structure:
            add_note(CACHE_STATUS_BAD_STRUCTURE)


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
            Token(
                "method"
            ): "The request method's semantics require the request to be forwarded.",
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


class CACHE_STATUS_BAD_STRUCTURE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The Cache-Status header has an invalid structure."
    _text = """\
The `Cache-Status` header must be a list of members, where each member is a 
Token or String (identifying the cache) with optional parameters.
"""


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


class CacheStatusTest(FieldTest):
    name = "Cache-Status"
    inputs = [b"ExampleCache; hit; ttl=3700", b"AnotherCache; fwd=uri-miss"]
    expected_out = [
        (Token("ExampleCache"), {"hit": True, "ttl": 3700}),
        (Token("AnotherCache"), {"fwd": Token("uri-miss")}),
    ]
    expected_notes = [CACHE_STATUS]


class CacheStatusUnknownParamTest(FieldTest):
    name = "Cache-Status"
    inputs = [b"ExampleCache; unknown=1"]
    expected_out = [(Token("ExampleCache"), {"unknown": 1})]
    expected_notes = [CACHE_STATUS_UNKNOWN_PARAM, CACHE_STATUS]


class CacheStatusBadParamValTest(FieldTest):
    name = "Cache-Status"
    inputs = [b"ExampleCache; fwd=invalid"]
    expected_out = [(Token("ExampleCache"), {"fwd": Token("invalid")})]
    expected_notes = [CACHE_STATUS_BAD_PARAM_VAL, CACHE_STATUS]
