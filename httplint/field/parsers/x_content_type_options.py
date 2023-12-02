from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class x_content_type_options(HttpField):
    reference = "https://fetch.spec.whatwg.org/#x-content-type-options-header"
    description = """\
Indicates that the client should not 'sniff' the `Content-Type` of the message from its content."""
    canonical_name = "X-Content-Type-Options"
    syntax = "nosniff"
    list_header = True
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
    level = levels.INFO
    _summary = "%(message)s instructs browsers not to 'sniff' its media type."
    _text = """\
Many Web browsers "sniff" the media type of responses to figure out whether they're HTML, RSS or
another format, no matter what the `Content-Type` header says.

This header instructs browsers not to do this, but to always respect the
Content-Type header. It probably won't have any effect in other clients.

See [this blog entry](http://bit.ly/t1UHW2) for more information about this header."""


class CONTENT_TYPE_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "%(message)s contains an X-Content-Type-Options header with an unknown value."
    )
    _text = """\
Only one value is currently defined for this header, `nosniff`. Using other values here won't
necessarily cause problems, but they probably won't have any effect either.

See [this blog entry](http://bit.ly/t1UHW2) for more information about this header."""
