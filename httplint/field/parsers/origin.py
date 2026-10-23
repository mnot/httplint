import re
from dataclasses import dataclass
from typing import Union

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import parse_digits
from httplint.note import Note, categories, levels
from httplint.syntax import rfc3986
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
)


@dataclass
class OriginValue:
    scheme: str
    host: str
    port: Union[int, None]


class origin(SingletonField[RequestLinterProtocol]):
    canonical_name = "Origin"
    description = """\
The `Origin` header field indicates where a fetch originates from. It is used to prevent Cross-Site
Request Forgery (CSRF) and in Cross-Origin Resource Sharing (CORS)."""
    reference = "https://www.rfc-editor.org/rfc/rfc6454.html#section-7"
    category = categories.CORS
    syntax = False
    deprecated = False

    max_port_digits = 20

    # serialized-origin = scheme "://" host [ ":" port ]
    serialized_origin_re = re.compile(
        rf"^(?P<scheme>{rfc3986.scheme})://(?P<host>{rfc3986.host})(?::(?P<port>{rfc3986.port}))?$",
        re.VERBOSE,
    )

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Union[None, OriginValue]:
        if field_value == "null":
            return None

        origins = field_value.split(" ")
        if len(origins) > 1:
            add_note(ORIGIN_MULTIPLE_VALUES)

        # only parse the first one
        match = self.serialized_origin_re.match(origins[0])
        if match:
            scheme = match.group("scheme").lower()
            host = match.group("host").lower()  # host is case insensitive
            port_str = match.group("port")
            port = None
            if port_str:
                port = parse_digits(port_str, self.max_port_digits)
                if port is None:
                    add_note(ORIGIN_PORT_TOO_LONG, max_digits=self.max_port_digits)
                    raise ValueError("Port too long in Origin")
            return OriginValue(scheme, host, port)

        add_note(BAD_ORIGIN_SYNTAX, value=origins[0])
        raise ValueError("Invalid value for Origin")


class BAD_ORIGIN_SYNTAX(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "%(value)s is not a valid origin."
    _text = """\
The Origin header must contain a list of serialized origins (scheme, host, and optional port), or
the string "null"."""


class ORIGIN_PORT_TOO_LONG(Note):
    category = categories.CORS
    level = levels.BAD
    _summary = "The Origin header contains a port with too many digits."
    _text = """\
The port in the `Origin` header has more than %(max_digits)s digits, which is more than recipients
can be expected to handle. Ports are 16-bit numbers (up to 65535)."""


class ORIGIN_MULTIPLE_VALUES(Note):
    category = categories.CORS
    level = levels.WARN
    _summary = "The Origin header contains multiple values."
    _text = """\
The `Origin` header should only contain a single value. Any values after the first
will be ignored."""


class OriginBasicTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"https://example.com"]
    expected_out: Union[None, OriginValue] = OriginValue("https", "example.com", None)


class OriginNullTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"null"]
    expected_out = None


class OriginMultipleTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"https://example.com http://example.org:8080"]
    expected_out = OriginValue("https", "example.com", None)
    expected_notes: NoteClassListType = [ORIGIN_MULTIPLE_VALUES]


class OriginBadSyntaxTest(FieldTest[RequestLinterProtocol]):
    name = "Origin"
    inputs = [b"https://example.com/foo"]
    expected_notes: NoteClassListType = [BAD_ORIGIN_SYNTAX]
    expected_out = None


class OriginPortTest(FieldTest[RequestLinterProtocol]):
    "Guard: a port out of range but of sane length is kept, without a note."

    name = "Origin"
    inputs = [b"https://example.com:99999"]
    expected_out = OriginValue("https", "example.com", 99999)


class OriginPortLeadingZerosTest(FieldTest[RequestLinterProtocol]):
    "Guard: leading zeros don't count towards the digit limit."

    name = "Origin"
    inputs = [b"https://example.com:" + b"0" * 30 + b"443"]
    expected_out = OriginValue("https", "example.com", 443)


class OriginEmptyPortTest(FieldTest[RequestLinterProtocol]):
    "Guard: an empty port is allowed by the grammar and means no port."

    name = "Origin"
    inputs = [b"https://example.com:"]
    expected_out = OriginValue("https", "example.com", None)


class OriginHugePortTest(FieldTest[RequestLinterProtocol]):
    "int() refuses long digit strings; the value must not be dropped silently."

    name = "Origin"
    inputs = [b"http://example.com:" + b"9" * 5000]
    expected_out = None
    expected_notes: NoteClassListType = [ORIGIN_PORT_TOO_LONG]


class OriginLongPortTest(OriginHugePortTest):
    "One digit over the limit."

    inputs = [b"http://example.com:" + b"1" * 21]
