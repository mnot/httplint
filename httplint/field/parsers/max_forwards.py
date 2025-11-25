from httplint.field import HttpField
from httplint.field.tests import FieldTest, FakeRequestLinter
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels


class MAX_FORWARDS_IGNORED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Max-Forwards header is ignored for this method."
    _text = """\
The `Max-Forwards` header is only defined for `TRACE` and `OPTIONS` requests; for other methods, it
is likely to be ignored."""


class max_forwards(HttpField):
    canonical_name = "Max-Forwards"
    description = """\
The `Max-Forwards` header field provides a mechanism to limit
the number of times that the request is forwarded by intermediaries."""
    reference = f"{rfc9110.SPEC_URL}#field.max-forwards"
    syntax = rfc9110.Max_Forwards
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if getattr(self.message, "message_type", None) != "request":
            return
        if getattr(self.message, "method", None) not in ["TRACE", "OPTIONS"]:
            add_note(MAX_FORWARDS_IGNORED)


class MaxForwardsTest(FieldTest):
    name = "Max-Forwards"
    inputs = [b"5"]
    expected_out = "5"

    def setUp(self) -> None:
        self.message = FakeRequestLinter()
        self.message.method = "TRACE"
        self.set_context(self.message)

    def test_trace_method(self) -> None:
        assert isinstance(self.message, FakeRequestLinter)
        self.message.method = "TRACE"
        self.inputs = [b"5"]
        self.expected_out = "5"
        self.expected_notes = []
        self.setUp()
        self.test_header()

    def test_options_method(self) -> None:
        assert isinstance(self.message, FakeRequestLinter)
        self.message.method = "OPTIONS"
        self.inputs = [b"5"]
        self.expected_out = "5"
        self.expected_notes = []
        self.setUp()
        self.test_header()

    def test_get_method(self) -> None:
        self.inputs = [b"5"]
        self.expected_out = "5"
        self.expected_notes = [MAX_FORWARDS_IGNORED]
        self.setUp()
        assert isinstance(self.message, FakeRequestLinter)
        self.message.method = "GET"
        self.test_header()
