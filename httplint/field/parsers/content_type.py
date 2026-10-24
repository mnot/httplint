from typing import Any, Tuple

from httplint.charset import normalise_label, whatwg_encoding
from httplint.charset_data import IANA_NAMES
from httplint.field.media_type import MEDIA_TYPE_BAD_NAME, MEDIA_TYPE_LONG_NAME, parse_media_type
from httplint.field.params import PARAM_REPEATS
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
    ParamDictType,
)


class content_type(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "Content-Type"
    description = """\
The `Content-Type` header indicates the media type of the content sent to the recipient or, in the
case of responses to the HEAD method, the media type that would have been sent had the request been
a GET."""
    reference = f"{rfc9110.SPEC_URL}#field.content-type"
    syntax = rfc9110.Content_Type
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        media_type, params = parse_media_type(field_value, add_note, nostar=["charset"])
        charset = params.get("charset")
        if isinstance(charset, str) and normalise_label(charset):
            check_charset(charset, add_note)
        return media_type, params


def check_charset(charset: str, add_note: AddNoteMethodType) -> None:
    """
    Check a charset name against the Encoding Standard, which is what recipients use
    to resolve it, and against the IANA registry, which RFC 9110 says names ought to
    come from.
    """
    encoding = whatwg_encoding(charset)
    if encoding is None:
        add_note(CHARSET_UNKNOWN, charset=charset)
    elif encoding == "replacement":
        add_note(CHARSET_REPLACEMENT, charset=charset)
    elif normalise_label(charset) not in IANA_NAMES:
        add_note(CHARSET_UNREGISTERED, charset=charset, encoding=encoding)


class CHARSET_UNKNOWN(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(charset)s' character encoding isn't one that recipients recognise."
    _text = """\
The `charset` parameter on the `%(field_name)s` field is `%(charset)s`, which isn't a label in the
[Encoding Standard](https://encoding.spec.whatwg.org/#names-and-labels). Browsers and other
recipients that follow it will ignore the parameter, and guess the encoding or use a default.

It might still be a valid name; the
[IANA registry](https://www.iana.org/assignments/character-sets) includes encodings such as
`UTF-7` and `UTF-32` that browsers don't support. Either way, it's unlikely to interoperate.
Consider `utf-8`."""


class CHARSET_REPLACEMENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(charset)s' character encoding is blocked by browsers."
    _text = """\
The `charset` parameter on the `%(field_name)s` field is `%(charset)s`. The
[Encoding Standard](https://encoding.spec.whatwg.org/#names-and-labels) maps this label to its
`replacement` encoding, which browsers don't decode; it does so because encodings like this one
can be used to inject crafted content.

Use an encoding that browsers support, such as `utf-8`."""


class CHARSET_UNREGISTERED(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The '%(charset)s' character encoding isn't a registered name."
    _text = """\
[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-charset) says that charset names
ought to be registered in the [IANA registry](https://www.iana.org/assignments/character-sets).
`%(charset)s` isn't in it.

Browsers recognise it, and treat it as `%(encoding)s`, but recipients that rely on the registry
might not. Use a registered name; for UTF-8, that's `utf-8`."""


class BasicCTTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-8"]
    expected_out = ("text/plain", {"charset": "utf-8"})


class CTSuffixTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"application/vnd.example.foo-bar+json"]
    expected_out: Any = ("application/vnd.example.foo-bar+json", {})


class CTBadNameTest(FieldTest[AnyMessageLinterProtocol]):
    "A media type that's a valid HTTP token, but not a valid RFC 6838 name."

    name = "Content-Type"
    inputs = [b"text/pl~in"]
    expected_out: Any = ("text/pl~in", {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_BAD_NAME]


class CTBadTypeNameTest(FieldTest[AnyMessageLinterProtocol]):
    "The type half is checked as well as the subtype half."

    name = "Content-Type"
    inputs = [b"~text/plain"]
    expected_out: Any = ("~text/plain", {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_BAD_NAME]


class CTBadNameFirstTest(FieldTest[AnyMessageLinterProtocol]):
    "RFC 6838 names have to start with a letter or a digit."

    name = "Content-Type"
    inputs = [b"text/.plain"]
    expected_out: Any = ("text/.plain", {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_BAD_NAME]


class CTLongNameTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/" + b"a" * 128]
    expected_out: Any = ("text/" + "a" * 128, {})
    expected_notes: NoteClassListType = [MEDIA_TYPE_LONG_NAME]


class CTCharsetRegisteredTest(FieldTest[AnyMessageLinterProtocol]):
    "Registered names and aliases, quoted or not, get no note."

    name = "Content-Type"
    inputs = [b'text/plain; charset="ISO-8859-1"']
    expected_out: Any = ("text/plain", {"charset": "ISO-8859-1"})


class CTCharsetLatin1AliasTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=latin1"]
    expected_out: Any = ("text/plain", {"charset": "latin1"})


class CTCharsetUnknownTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=nonesuch"]
    expected_out: Any = ("text/plain", {"charset": "nonesuch"})
    expected_notes: NoteClassListType = [CHARSET_UNKNOWN]


class CTCharsetRegisteredNotLabelledTest(FieldTest[AnyMessageLinterProtocol]):
    "UTF-7 is in the IANA registry, but browsers don't support it."

    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-7"]
    expected_out: Any = ("text/plain", {"charset": "utf-7"})
    expected_notes: NoteClassListType = [CHARSET_UNKNOWN]


class CTCharsetPythonOnlyTest(FieldTest[AnyMessageLinterProtocol]):
    "Python has a codec by this name; recipients don't."

    name = "Content-Type"
    inputs = [b"text/plain; charset=unicode_escape"]
    expected_out: Any = ("text/plain", {"charset": "unicode_escape"})
    expected_notes: NoteClassListType = [CHARSET_UNKNOWN]


class CTCharsetReplacementTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=iso-2022-kr"]
    expected_out: Any = ("text/plain", {"charset": "iso-2022-kr"})
    expected_notes: NoteClassListType = [CHARSET_REPLACEMENT]


class CTCharsetUnregisteredTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Content-Type"
    inputs = [b"text/plain; charset=utf8"]
    expected_out: Any = ("text/plain", {"charset": "utf8"})
    expected_notes: NoteClassListType = [CHARSET_UNREGISTERED]


class CTCharsetEmptyTest(FieldTest[AnyMessageLinterProtocol]):
    "Nothing to say about an empty name."

    name = "Content-Type"
    inputs = [b'text/plain; charset=""']
    expected_out: Any = ("text/plain", {"charset": ""})


class CTRepeatedCharsetTest(FieldTest[AnyMessageLinterProtocol]):
    "The first charset counts, as in the MIME Sniffing Standard; the repeat is noted."

    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-8; charset=nonesuch"]
    expected_out: Any = ("text/plain", {"charset": "utf-8"})
    expected_notes: NoteClassListType = [PARAM_REPEATS]
