from typing import Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params
from httplint.field.notes import BAD_SYNTAX


class x_xss_protection(HttpField):
    canonical_name = "X-XSS-Protection"
    description = """\
The `X-XSS-Protection` response header can be sent by servers to control how
older versions of Internet Explorer configure their Cross Site Scripting protection."""
    reference = (
        "https://blogs.msdn.microsoft.com/ieinternals/"
        "2011/01/31/controlling-the-xss-filter/"
    )
    syntax = rf"(?:[10](?:\s*;\s*{rfc7231.parameter})*)"
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[int, ParamDictType]:
        try:
            protect, param_str = field_value.split(";", 1)
        except ValueError:
            protect, param_str = field_value, ""
        protect_int = int(protect)
        params = parse_params(param_str, add_note, True)
        if protect_int == 0:
            add_note(XSS_PROTECTION_OFF)
        else:  # 1
            if params.get("mode", None) == "block":
                add_note(XSS_PROTECTION_BLOCK)
            else:
                add_note(XSS_PROTECTION_ON)
        return protect_int, params


class XSS_PROTECTION_ON(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s enables XSS filtering in IE8+."
    _text = """\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

%(message)s has explicitly enabled this protection. If IE detects a Cross-site scripting attack,
it will "sanitise" the page to prevent the attack. In other words, the page will still render.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""


class XSS_PROTECTION_OFF(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s disables XSS filtering in IE8+."
    _text = """\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

%(message)s has explicitly disabled this protection. In some scenarios, this is useful to do, if
the protection interferes with the application.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""


class XSS_PROTECTION_BLOCK(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "%(message)s blocks XSS attacks in IE8+."
    _text = """\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

Usually, IE will rewrite the attacking HTML, so that the attack is neutralised, but the content can
still be seen. %(message)s instructs IE to not show such pages at all, but rather to display an
error.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""


class OneXXSSTest(FieldTest):
    name = "X-XSS-Protection"
    inputs = [b"1"]
    expected_out = (1, {})  # type: ignore
    expected_notes = [XSS_PROTECTION_ON]


class ZeroXXSSTest(FieldTest):
    name = "X-XSS-Protection"
    inputs = [b"0"]
    expected_out = (0, {})  # type: ignore
    expected_notes = [XSS_PROTECTION_OFF]


class OneBlockXXSSTest(FieldTest):
    name = "X-XSS-Protection"
    inputs = [b"1; mode=block"]
    expected_out = (1, {"mode": "block"})
    expected_notes = [XSS_PROTECTION_BLOCK]


class BadXXSSTest(FieldTest):
    name = "X-XSS-Protection"
    inputs = [b"foo"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]
