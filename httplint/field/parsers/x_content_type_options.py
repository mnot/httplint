from httplint.field import HttpField
from httplint.field import BAD_SYNTAX
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class x_content_type_options(HttpField):
    reference = "https://fetch.spec.whatwg.org/#x-content-type-options-header"
    description = """\
Indicates that the client should not 'sniff' the `Content-Type` of the message from its content."""
    canonical_name = "X-Content-Type-Options"
    syntax = "nosniff"
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "nosniff" in self.value:
            add_note(CONTENT_TYPE_OPTIONS)
        else:
            add_note(CONTENT_TYPE_OPTIONS_UNKNOWN)


class CONTENT_TYPE_OPTIONS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response instructs browsers not to 'sniff' its media type."
    # Original URL:
    # http://blogs.msdn.com/b/ie/archive/2008/09/02/ie8-security-part-vi-beta-2-update.aspx
    _text = """\
Many Web browsers "sniff" the media type of responses to figure out whether they're HTML, RSS or
another format, no matter what the `Content-Type` header says.

This header instructs browsers not to do this, but to always respect the
Content-Type header. It probably won't have any effect in other clients.

See [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options)
for more information about this header."""


class CONTENT_TYPE_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "X-Content-Type-Options contains an unknown value."
    # Original URL:
    # http://blogs.msdn.com/b/ie/archive/2008/09/02/ie8-security-part-vi-beta-2-update.aspx
    _text = """\
Only one value is currently defined for this header, `nosniff`. Using other values here won't
necessarily cause problems, but they probably won't have any effect either.

See [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options)
for more information about this header."""


class XContentTypeOptionsTest(FieldTest):
    name = "X-Content-Type-Options"
    inputs = [b"nosniff", b"foo"]
    expected_out = ["nosniff", "foo"]
    expected_notes = [CONTENT_TYPE_OPTIONS, BAD_SYNTAX]
