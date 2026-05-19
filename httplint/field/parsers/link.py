import re
from typing import Tuple
from urllib.parse import urljoin, urlsplit

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import PARAM_REPEATS, parse_params
from httplint.note import Note, categories, levels
from httplint.syntax import rfc3986, rfc8288, rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
    ParamDictType,
)


class link(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Link"
    description = """\
The `Link` header allows links related to the content to be conveyed. A link can be viewed as a
statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has
[target attributes]."""
    reference = f"{rfc8288.SPEC_URL}#header.link"
    syntax = rfc8288.Link
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
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
            if not re.match(rf"^\s*{rfc3986.URI_reference}\s*$", param_dict["anchor"], re.VERBOSE):
                add_note(LINK_BAD_ANCHOR, link=link_value, anchor=param_dict["anchor"])
        if "type" in param_dict and param_dict["type"]:
            if not re.match(rf"^\s*{rfc9110.media_type}\s*$", param_dict["type"], re.VERBOSE):
                add_note(LINK_BAD_TYPE, link=link_value, type=param_dict["type"])
        return link_value, param_dict

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        hints: dict[str, list[str]] = {"preload": [], "preconnect": [], "dns-prefetch": []}
        bad_targets: list[Tuple[str, str, str]] = []  # (rel, link, scheme)
        base_uri = getattr(self.message, "base_uri", "") or ""
        for link_value, params in self.value:
            rel = params.get("rel")
            if not isinstance(rel, str):
                continue
            for token in rel.lower().split():
                if token not in hints:
                    continue
                scheme = urlsplit(urljoin(base_uri, link_value)).scheme.lower()
                if scheme and scheme not in ("http", "https"):
                    bad_targets.append((token, link_value, scheme))
                else:
                    hints[token].append(link_value)

        for rel_name, link_value, scheme in bad_targets:
            add_note(LINK_BAD_HINT_TARGET, rel=rel_name, link=link_value, scheme=scheme)

        present = {k: v for k, v in hints.items() if v}
        if present:
            hints_plain = ", ".join(present)
            # Strip backticks so attacker-controlled link targets cannot escape
            # the surrounding code span and inject raw HTML via Markdown.
            lines = []
            for rel_name, targets in present.items():
                safe = [t.replace("`", "") for t in targets]
                lines.append(f"- `{rel_name}`: {', '.join(f'`{t}`' for t in safe)}")
            add_note(
                LINK_RESOURCE_HINTS,
                hints=hints_plain,
                detail_lines="\n".join(lines),
            )


class LINK_RESOURCE_HINTS(Note):
    category = categories.GENERAL
    level = levels.GOOD
    _summary = "This response provides resource hints (%(hints)s)."
    _text = """\
The `Link` header advertises the following
[resource hints](https://www.w3.org/TR/resource-hints/), allowing the client to begin work on
related resources before the current response is fully processed:

%(detail_lines)s

`preload` triggers the browser to fetch a resource needed for the current page; `preconnect`
opens a connection (DNS + TCP + TLS) to an origin in advance; `dns-prefetch` performs a DNS
lookup only. Used appropriately, these hints can reduce critical-path latency."""


class LINK_BAD_HINT_TARGET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(rel)s Link target uses an unsupported scheme."
    _text = """\
The `Link` header advertises a `%(rel)s` resource hint for `%(link)s`, but its scheme
(`%(scheme)s`) is not `http` or `https`. Browsers will ignore this hint."""


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


class BasicLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"<http://www.example.com/>; rel=example"]
    expected_out = [("http://www.example.com/", {"rel": "example"})]


class QuotedLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'"http://www.example.com/"; rel=example']
    expected_out = [("http://www.example.com/", {"rel": "example"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class QuotedRelationLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'<http://www.example.com/>; rel="example"']
    expected_out = [("http://www.example.com/", {"rel": "example"})]


class RelativeLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</foo>; rel="example"']
    expected_out = [("/foo", {"rel": "example"})]


class RepeatingRelationLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</foo>; rel="example"; rel="another"']
    expected_out = [("/foo", {"rel": "another"})]
    expected_notes: NoteClassListType = [PARAM_REPEATS]


class RevLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</foo>; rev="bar"']
    expected_out = [("/foo", {"rev": "bar"})]
    expected_notes: NoteClassListType = [LINK_REV]


class BadAnchorLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</foo>; rel="bar"; anchor="{blah}"']
    expected_out = [("/foo", {"rel": "bar", "anchor": "{blah}"})]
    expected_notes: NoteClassListType = [LINK_BAD_ANCHOR]


class BadTypeLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</foo>; rel="bar"; type="{blah}"']
    expected_out = [("/foo", {"rel": "bar", "type": "{blah}"})]
    expected_notes: NoteClassListType = [LINK_BAD_TYPE]


class PreloadLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</main.css>; rel="preload"; as="style"']
    expected_out = [("/main.css", {"rel": "preload", "as": "style"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class PreconnectLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'<https://cdn.example.com>; rel="preconnect"']
    expected_out = [("https://cdn.example.com", {"rel": "preconnect"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class DnsPrefetchLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'<https://cdn.example.com>; rel="dns-prefetch"']
    expected_out = [("https://cdn.example.com", {"rel": "dns-prefetch"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class MultipleHintsLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [
        b'</main.css>; rel="preload"; as="style"',
        b'<https://cdn.example.com>; rel="preconnect"',
    ]
    expected_out = [
        ("/main.css", {"rel": "preload", "as": "style"}),
        ("https://cdn.example.com", {"rel": "preconnect"}),
    ]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class CombinedRelHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'<https://cdn.example.com>; rel="preconnect dns-prefetch"']
    expected_out = [("https://cdn.example.com", {"rel": "preconnect dns-prefetch"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class NonHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'</style.css>; rel="stylesheet"']
    expected_out = [("/style.css", {"rel": "stylesheet"})]
    expected_notes: NoteClassListType = []


class BadHintTargetLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'<javascript:alert(1)>; rel="preload"']
    expected_out = [("javascript:alert(1)", {"rel": "preload"})]
    expected_notes: NoteClassListType = [LINK_BAD_HINT_TARGET]


class MixedHintTargetsLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [
        b'<https://cdn.example.com>; rel="preconnect"',
        b'<ftp://example.com/x>; rel="preload"',
    ]
    expected_out = [
        ("https://cdn.example.com", {"rel": "preconnect"}),
        ("ftp://example.com/x", {"rel": "preload"}),
    ]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS, LINK_BAD_HINT_TARGET]
