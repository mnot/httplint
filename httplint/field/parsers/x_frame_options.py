from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc3986, rfc9110
from httplint.types import AddNoteMethodType, NoteClassListType, ResponseLinterProtocol

# X-Frame-Options = "DENY"
#          / "SAMEORIGIN"
#          / ( "ALLOW-FROM" RWS SERIALIZED-ORIGIN )

# pylint: disable=invalid-name  # names mirror ABNF rule names
serialized_origin = rf"""(?:
{rfc3986.scheme} :// {rfc3986.host} (?: : {rfc3986.port} )?
)
"""

X_Frame_Options = rf"""(?:
      DENY
    | SAMEORIGIN
    | (?: ALLOW-FROM {rfc9110.RWS} {serialized_origin} )
)"""
# pylint: enable=invalid-name


class x_frame_options(SingletonField[ResponseLinterProtocol]):
    canonical_name = "X-Frame-Options"
    reference = "https://www.rfc-editor.org/rfc/rfc7034"
    description = """
The X-Frame-Options response header declares a policy regarding whether the browser may display
the transmitted content in frames that are part of other web pages.
"""
    syntax = X_Frame_Options
    category = categories.SECURITY
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.upper()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "DENY" in self.value:
            add_note(FRAME_OPTIONS_DENY)
        elif "SAMEORIGIN" in self.value:
            add_note(FRAME_OPTIONS_SAMEORIGIN)
        else:
            add_note(FRAME_OPTIONS_UNKNOWN)


class FRAME_OPTIONS_DENY(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response prevents browsers from rendering it within a frame."
    _text = """\
The `DENY` value of `X-Frame-Options` prevents this content from being rendered within a frame,
defending against clickjacking-style attacks.

Note that `X-Frame-Options` has been superseded by the
[`frame-ancestors`](https://www.w3.org/TR/CSP3/#directive-frame-ancestors) directive of
`Content-Security-Policy`, which offers finer-grained control and is the modern equivalent.
If both are present, browsers that support CSP will use `frame-ancestors` and ignore this header.

See [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options) for more information.
"""


class FRAME_OPTIONS_SAMEORIGIN(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response prevents browsers from rendering it within a frame on another site."
    _text = """\
The `SAMEORIGIN` value of `X-Frame-Options` prevents this content from being rendered within a
frame on a different origin, defending against clickjacking-style attacks.

Note that `X-Frame-Options` has been superseded by the
[`frame-ancestors`](https://www.w3.org/TR/CSP3/#directive-frame-ancestors) directive of
`Content-Security-Policy`, which offers finer-grained control and is the modern equivalent.
If both are present, browsers that support CSP will use `frame-ancestors` and ignore this header.

See [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options) for more information.
"""


class FRAME_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The X-Frame-Options header contains an unknown value."
    # Original URL:
    # http://blogs.msdn.com/b/ie/archive/2009/01/27/ie8-security-part-vii-clickjacking-defenses.aspx
    _text = """\
Only two values are currently defined for this header, `DENY` and `SAMEORIGIN`. Using other values
here won't necessarily cause problems, but they probably won't have any effect either.

See [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options) for more information.
"""


class DenyXFOTest(FieldTest[ResponseLinterProtocol]):
    name = "X-Frame-Options"
    inputs = [b"DENY"]
    expected_out = "DENY"
    expected_notes: NoteClassListType = [FRAME_OPTIONS_DENY]


class DenyXFOCaseTest(FieldTest[ResponseLinterProtocol]):
    name = "X-Frame-Options"
    inputs = [b"deny"]
    expected_out = "DENY"
    expected_notes: NoteClassListType = [FRAME_OPTIONS_DENY]


class SameOriginXFOTest(FieldTest[ResponseLinterProtocol]):
    name = "X-Frame-Options"
    inputs = [b"SAMEORIGIN"]
    expected_out = "SAMEORIGIN"
    expected_notes: NoteClassListType = [FRAME_OPTIONS_SAMEORIGIN]


class UnknownXFOTest(FieldTest[ResponseLinterProtocol]):
    name = "X-Frame-Options"
    inputs = [b"foO"]
    expected_out = "FOO"
    expected_notes: NoteClassListType = [BAD_SYNTAX, FRAME_OPTIONS_UNKNOWN]
