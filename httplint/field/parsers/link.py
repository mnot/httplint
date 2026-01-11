import re
from typing import Tuple
from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc3986, rfc8288, rfc9110
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params
from httplint.field.utils import PARAM_REPEATS
from httplint.field import BAD_SYNTAX


class link(HttpField):
    canonical_name = "Link"
    description = """\
The `Link` header allows links related to the content to be conveyed. A link can be viewed as a
statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has
[target attributes]."""
    reference = f"{rfc8288.SPEC_URL}#header.link"
    syntax = rfc8288.Link
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        try:
            link_value, param_str = field_value.split(";", 1)
        except ValueError:
            link_value, param_str = field_value, ""
        link_value = link_value.strip()[1:-1]  # trim the angle brackets
        param_dict = parse_params(
            param_str, add_note, ["rel", "rev", "anchor", "hreflang", "type", "media"]
        )
        if "rel" in param_dict:  # relation_types
            pass
        if "rev" in param_dict:
            add_note(LINK_REV, link=link_value, rev=str(param_dict["rev"]))
        if "anchor" in param_dict and param_dict["anchor"]:  # URI-Reference
            if not re.match(
                rf"^\s*{rfc3986.URI_reference}\s*$", param_dict["anchor"], re.VERBOSE
            ):
                add_note(LINK_BAD_ANCHOR, link=link_value, anchor=param_dict["anchor"])
        if "type" in param_dict and param_dict["type"]:
            if not re.match(
                rf"^\s*{rfc9110.media_type}\s*$", param_dict["type"], re.VERBOSE
            ):
                add_note(LINK_BAD_TYPE, link=link_value, type=param_dict["type"])
        return link_value, param_dict


class LINK_REV(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The 'rev' parameter on the Link header is deprecated."
    _text = """\
The `Link` header, defined by [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288#section-3), uses the
`rel` parameter to communicate the type of a link. `rev` is deprecated by that specification
because it is often confusing.

Use `rel` and an appropriate relation."""


class LINK_BAD_ANCHOR(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The 'anchor' parameter on the %(link)s Link header isn't a URI."
    _text = """\
The `Link` header, defined by [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288#section-3), uses the
`anchor` parameter to define the context URI for the link.

This parameter can be an absolute or relative URI; however, `%(anchor)s` is neither."""


class LINK_BAD_TYPE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The 'type' parameter on the %(link)s Link header isn't a media type."
    _text = """\
The `Link` header, defined by [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288#section-3), uses the
`type` parameter to define the media type of the link target.

However, `%(type)s` is not a valid media type."""


class BasicLinkTest(FieldTest):
    name = "Link"
    inputs = [b"<http://www.example.com/>; rel=example"]
    expected_out = [("http://www.example.com/", {"rel": "example"})]


class QuotedLinkTest(FieldTest):
    name = "Link"
    inputs = [b'"http://www.example.com/"; rel=example']
    expected_out = [("http://www.example.com/", {"rel": "example"})]
    expected_notes = [BAD_SYNTAX]


class QuotedRelationLinkTest(FieldTest):
    name = "Link"
    inputs = [b'<http://www.example.com/>; rel="example"']
    expected_out = [("http://www.example.com/", {"rel": "example"})]


class RelativeLinkTest(FieldTest):
    name = "Link"
    inputs = [b'</foo>; rel="example"']
    expected_out = [("/foo", {"rel": "example"})]


class RepeatingRelationLinkTest(FieldTest):
    name = "Link"
    inputs = [b'</foo>; rel="example"; rel="another"']
    expected_out = [("/foo", {"rel": "another"})]
    expected_notes = [PARAM_REPEATS]


class RevLinkTest(FieldTest):
    name = "Link"
    inputs = [b'</foo>; rev="bar"']
    expected_out = [("/foo", {"rev": "bar"})]
    expected_notes = [LINK_REV]


class BadAnchorLinkTest(FieldTest):
    name = "Link"
    inputs = [b'</foo>; rel="bar"; anchor="{blah}"']
    expected_out = [("/foo", {"rel": "bar", "anchor": "{blah}"})]
    expected_notes = [LINK_BAD_ANCHOR]


class BadTypeLinkTest(FieldTest):
    name = "Link"
    inputs = [b'</foo>; rel="bar"; type="{blah}"']
    expected_out = [("/foo", {"rel": "bar", "type": "{blah}"})]
    expected_notes = [LINK_BAD_TYPE]
