"""Helpers for list fields whose members must be a Structured Field String or Token."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Tuple

from http_sf import DisplayString, Token
from http_sf.list import ser_list

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


def member_type_phrase(member: Any) -> str:
    "The type name with its indefinite article, such as 'an Integer' or 'a Date'."
    name = member_type_name(member)
    return f"{'an' if name[0] in 'AEIOU' else 'a'} {name}"


def member_text(member: Any) -> str:
    'A String or Token as its text; any other member in its wire form, such as ?1 or (a "").'
    if is_string_or_token(member):
        return str(member)
    try:
        return str(ser_list([(member, {})]))
    except ValueError:
        return str(member)
