"""Helpers for list fields whose members must be a Structured Field String or Token."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Tuple

from http_sf import DisplayString, Token

_TYPE_NAMES: Tuple[Tuple[type, str], ...] = (
    (bool, "Boolean"),
    (int, "Integer"),
    (Decimal, "Decimal"),
    (bytes, "Byte Sequence"),
    (DisplayString, "Display String"),
    (datetime, "Date"),
    (list, "Inner List"),
    (Token, "Token"),
)


def is_string_or_token(member: Any) -> bool:
    "True if `member` (a parsed list member's value) is an SF String or Token."
    return isinstance(member, (str, Token))


def member_type_name(member: Any) -> str:
    "The Structured Field type name of a parsed list member's value."
    for expected, type_name in _TYPE_NAMES:  # bool first: it is an int subclass
        if isinstance(member, expected):
            return type_name
    return "String"


def member_text(member: Any) -> str:
    "Plain text for a member; an inner list is shown as (a b), not as a Python repr."
    if isinstance(member, bytes):
        return member.decode("ascii", "replace")
    if isinstance(member, list):
        return "(" + " ".join(member_text(item) for item, _ in member) + ")"
    return str(member)
