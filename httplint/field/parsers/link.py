import re
from typing import Tuple

from httplint.field import BAD_SYNTAX
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.field.utils import (
    PARAM_REPEATS,
    PARAM_STAR_ERROR,
    parse_params,
    resolve_url,
)
from httplint.note import MarkdownSafe, Note, categories, levels
from httplint.syntax import rfc3986, rfc8288, rfc9110
from httplint.types import (
    AddNoteMethodType,
    AnyMessageLinterProtocol,
    NoteClassListType,
    ParamDictType,
)
from httplint.util import inline_safe

HINT_RELS = ("preload", "preconnect", "dns-prefetch")


def split_link_value(field_value: str) -> Tuple[str, str]:
    """
    Split a link-value into its target and its parameter string.

    A target in angle brackets ends at the first ">"; a ";" inside it is part of the URI.
    Anything else isn't a valid link-value, so the target is the text before the first ";",
    unchanged.
    """
    value = field_value.strip()
    if value.startswith("<") and ">" in value:
        target, _, rest = value[1:].partition(">")
        return target, rest.partition(";")[2]
    target, _, params = value.partition(";")
    return target.strip(), params


class link(HttpListField[AnyMessageLinterProtocol]):
    canonical_name = "Link"
    description = """\
The `Link` header allows links related to the content to be conveyed. A link can be viewed as a
statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has
[target attributes]."""
    reference = f"{rfc8288.SPEC_URL}#header.link"
    syntax = rfc8288.Link
    deprecated = False

    def __init__(self, wire_name: str, message: AnyMessageLinterProtocol) -> None:
        super().__init__(wire_name, message)
        self.malformed: set[int] = set()  # id() of the params of links with a syntax defect
        self._params: ParamDictType = {}  # the params parse() last returned

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        link_value, param_str = split_link_value(field_value)
        param_dict = parse_params(
            param_str, add_note, ["rel", "rev", "anchor", "hreflang", "type", "media"]
        )
        self._params = param_dict
        self._check_hint_target(link_value, param_dict, add_note)
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

    def _check_hint_target(
        self, link_value: str, params: ParamDictType, add_note: AddNoteMethodType
    ) -> bool:
        "Add LINK_BAD_TARGET_URI if a resource hint's target is unresolvable; True if so."
        rel = params.get("rel")
        if not isinstance(rel, str):
            return False
        hint_rels = [t for t in dict.fromkeys(rel.lower().split()) if t in HINT_RELS]
        if not hint_rels:
            return False
        base_uri = getattr(self.message, "base_uri", "") or ""
        if resolve_url(link_value, base_uri) is not None:
            return False
        add_note(LINK_BAD_TARGET_URI, rel="/".join(hint_rels), link=link_value)
        self.suppress_syntax_note()
        return True

    def _check_syntax(self, value: str, add_note: AddNoteMethodType) -> bool:
        "The base class checks each link after parse(); remember the ones that fail."
        conforms = super()._check_syntax(value, add_note)
        if not conforms:
            self.malformed.add(id(self._params))
        return conforms

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        hints: dict[str, list[str]] = {rel: [] for rel in HINT_RELS}
        bad_targets: list[Tuple[str, str, str]] = []  # (rel, link, scheme)
        base_uri = getattr(self.message, "base_uri", "") or ""
        for link_value, params in self.value:
            rel = params.get("rel")
            if not isinstance(rel, str) or id(params) in self.malformed:
                continue
            for token in rel.lower().split():
                if token not in hints:
                    continue
                resolved = resolve_url(link_value, base_uri)
                if resolved is None:
                    continue  # reported by parse()
                scheme = resolved.scheme.lower()
                if scheme and scheme not in ("http", "https"):
                    bad_targets.append((token, link_value, scheme))
                else:
                    hints[token].append(link_value)

        for rel_name, link_value, scheme in bad_targets:
            add_note(LINK_BAD_HINT_TARGET, rel=rel_name, link=link_value, scheme=scheme)

        present = {k: v for k, v in hints.items() if v}
        if present:
            hints_plain = ", ".join(present)
            lines = []
            for rel_name, targets in present.items():
                safe = [inline_safe(t) for t in targets]
                lines.append(f"- `{rel_name}`: {', '.join(f'`{t}`' for t in safe)}")
            add_note(
                LINK_RESOURCE_HINTS,
                hints=hints_plain,
                detail_lines=MarkdownSafe("\n".join(lines)),
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


class LINK_BAD_TARGET_URI(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(rel)s Link target isn't a valid URI."
    _text = """\
The `Link` header advertises a `%(rel)s` resource hint for `%(link)s`, but that isn't a valid URI
(for example, it may have a malformed IP address in its host). Browsers may ignore this hint."""


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
    "Only a target in angle brackets is unwrapped; this one keeps its quotes."

    name = "Link"
    inputs = [b'"http://www.example.com/"; rel=example']
    expected_out = [('"http://www.example.com/"', {"rel": "example"})]
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
    "RFC 8288 Section 3.3: occurrences after the first are ignored."

    name = "Link"
    inputs = [b'</foo>; rel="example"; rel="another"']
    expected_out = [("/foo", {"rel": "example"})]
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


class RepeatedRejectedTitleStarLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "The first title* is the one that counts, even though it's rejected."

    name = "Link"
    inputs = [b"</foo>; rel=ex; title*=bogus; title*=UTF-8''%41"]
    expected_out = [("/foo", {"rel": "ex"})]
    expected_notes: NoteClassListType = [PARAM_STAR_ERROR, PARAM_REPEATS]


class MalformedIPv6PreloadLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"<http://[::1>; rel=preload"]
    expected_out = [("http://[::1", {"rel": "preload"})]
    expected_notes: NoteClassListType = [LINK_BAD_TARGET_URI]


class MalformedIPv6PreconnectLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"<http://[::1]x>; rel=preconnect"]
    expected_out = [("http://[::1]x", {"rel": "preconnect"})]
    expected_notes: NoteClassListType = [LINK_BAD_TARGET_URI]


class MalformedIPv6OtherRelLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "Only resource hint targets are resolved, so other links keep BAD_SYNTAX."

    name = "Link"
    inputs = [b"<http://[::1>; rel=stylesheet"]
    expected_out = [("http://[::1", {"rel": "stylesheet"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class BadSyntaxHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "A syntax error that isn't an unresolvable target is still BAD_SYNTAX, with no hint note."

    name = "Link"
    inputs = [b"</a b>; rel=preload"]
    expected_out = [("/a b", {"rel": "preload"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class SemicolonInTargetLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "A ';' inside the angle brackets is part of the URI, not a parameter delimiter."

    name = "Link"
    inputs = [b"<http://example.com/a;b>; rel=next"]
    expected_out = [("http://example.com/a;b", {"rel": "next"})]


class SemicolonInHintTargetLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"<http://example.com/a;b=c>; rel=preload; as=script"]
    expected_out = [("http://example.com/a;b=c", {"rel": "preload", "as": "script"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]


class GreaterThanInParamLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "Only the first '>' ends the target; later ones belong to the parameters."

    name = "Link"
    inputs = [b'</foo>; rel=next; title="a>b"']
    expected_out = [("/foo", {"rel": "next", "title": "a>b"})]


class UnbracketedTargetLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "Without angle brackets nothing is stripped from the target."

    name = "Link"
    inputs = [b"foo; rel=preload"]
    expected_out = [("foo", {"rel": "preload"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class UnclosedBracketLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"<http://example.com/; rel=next"]
    expected_out = [("<http://example.com/", {"rel": "next"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class TrailingGarbageAfterTargetLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"</foo>x; rel=next"]
    expected_out = [("/foo", {"rel": "next"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class UnclosedBracketHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "A malformed link doesn't get the resource hint note."

    name = "Link"
    inputs = [b"<http://example.com/x; rel=preload"]
    expected_out = [("<http://example.com/x", {"rel": "preload"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class QuotedHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b'"http://example.com/x"; rel=preconnect']
    expected_out = [('"http://example.com/x"', {"rel": "preconnect"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class UnbracketedHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Link"
    inputs = [b"http://example.com/x; rel=dns-prefetch"]
    expected_out = [("http://example.com/x", {"rel": "dns-prefetch"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class TrailingGarbageHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "BAD_SYNTAX_DETAILED, which the base class adds, also means no hint note."

    name = "Link"
    inputs = [b"</foo>x; rel=preload"]
    expected_out = [("/foo", {"rel": "preload"})]
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class WellFormedHintLinkTest(FieldTest[AnyMessageLinterProtocol]):
    "Guard: a well-formed hint link, with other parameters, still gets its note."

    name = "Link"
    inputs = [b'</a;b.css>; rel="preload"; as=style; type="text/css"']
    expected_out = [("/a;b.css", {"rel": "preload", "as": "style", "type": "text/css"})]
    expected_notes: NoteClassListType = [LINK_RESOURCE_HINTS]
