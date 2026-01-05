from typing import List, NamedTuple, Union
import re

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc3986
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels


class OriginValue(NamedTuple):
    scheme: str
    host: str
    port: Union[int, None]


class origin(SingletonField):
    canonical_name = "Origin"
    description = """\
The `Origin` header field indicates where a fetch originates from. It is used to prevent Cross-Site
Request Forgery (CSRF) and in Cross-Origin Resource Sharing (CORS)."""
    reference = "https://www.rfc-editor.org/rfc/rfc6454.html#section-7"
    syntax = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    # serialized-origin = scheme "://" host [ ":" port ]
    serialized_origin_re = re.compile(
        rf"^(?P<scheme>{rfc3986.scheme})://(?P<host>{rfc3986.host})(?::(?P<port>{rfc3986.port}))?$",
        re.VERBOSE,
    )

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Union[str, List[OriginValue]]:
        if field_value == "null":
            return "null"

        origins = []
        for item in field_value.split(" "):
            match = self.serialized_origin_re.match(item)
            if match:
                scheme = match.group("scheme").lower()
                host = match.group("host").lower()  # host is case insensitive
                port_str = match.group("port")
                port = int(port_str) if port_str else None
                origins.append(OriginValue(scheme, host, port))
            else:
                add_note(BAD_ORIGIN_SYNTAX, value=item)

        return origins


class BAD_ORIGIN_SYNTAX(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "%(value)s is not a valid origin."
    _text = """\
The Origin header must contain a list of serialized origins (scheme, host, and optional port), or
the string "null"."""


class OriginTest(FieldTest):
    name = "Origin"
    inputs = [b"https://example.com"]
    expected_out: Union[str, List[OriginValue]] = [OriginValue("https", "example.com", None)]

    def test_null(self) -> None:
        self.inputs = [b"null"]
        self.expected_out = "null"
        self.setUp()
        self.test_header()

    def test_multiple(self) -> None:
        self.inputs = [b"https://example.com http://example.org:8080"]
        self.expected_out = [
            OriginValue("https", "example.com", None),
            OriginValue("http", "example.org", 8080),
        ]
        self.setUp()
        self.test_header()

    def test_bad_syntax(self) -> None:
        self.inputs = [b"https://example.com/foo"]
        self.expected_notes = [BAD_ORIGIN_SYNTAX]
        self.expected_out = []
        self.setUp()
        self.test_header()
