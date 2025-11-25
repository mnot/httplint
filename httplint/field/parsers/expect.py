from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels


class expect(HttpField):
    canonical_name = "Expect"
    description = """\
The `Expect` header field in a request indicates behaviors (expectations) that need to be
fulfilled by the server in order to properly handle the request."""
    reference = f"{rfc9110.SPEC_URL}#field.expect"
    syntax = rfc9110.Expect
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self.message.version == "1.0":
            add_note(EXPECT_HTTP_1_0)

        unknown_expectations = []
        for expectation in self.value:
            if expectation.lower() == "100-continue":
                continue
            unknown_expectations.append(expectation)

        if unknown_expectations:
            add_note(EXPECT_UNKNOWN, expectation=", ".join(unknown_expectations))


class EXPECT_UNKNOWN(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(expectation)s' expectation is not supported."
    _text = """\
HTTP only defines one expectation, `100-continue`. This expectation is not recognized."""


class EXPECT_HTTP_1_0(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The Expect header is not supported in HTTP/1.0."
    _text = """\
The `Expect` header was added in HTTP/1.1; it has no meaning in HTTP/1.0."""


class ExpectTest(FieldTest):
    name = "Expect"
    inputs = [b"100-continue"]
    expected_out = ["100-continue"]
    expected_notes = []

    def test_unknown(self) -> None:
        self.inputs = [b"foo"]
        self.expected_out = ["foo"]
        self.expected_notes = [EXPECT_UNKNOWN]
        self.setUp()
        self.test_header()

    def test_multiple_unknown(self) -> None:
        self.inputs = [b"foo", b"bar"]
        self.expected_out = ["foo", "bar"]
        self.expected_notes = [EXPECT_UNKNOWN]
        self.setUp()
        self.test_header()

    def test_http_1_0(self) -> None:
        self.inputs = [b"100-continue"]
        self.expected_out = ["100-continue"]
        self.expected_notes = [EXPECT_HTTP_1_0]
        self.setUp()
        self.message.version = "1.0"
        self.test_header()
