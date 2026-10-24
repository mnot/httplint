"""
Content-coding helpers shared by Accept-Encoding, Content-Encoding and Available-Dictionary.
"""

from typing import Dict, Iterable, List, Optional, Tuple

from httplint.field.utils import parse_qvalue
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, ParamDictType

# RFC 9110 Section 8.4.1: a recipient SHOULD consider these legacy names equivalent.
CODING_ALIASES = {"x-gzip": "gzip", "x-compress": "compress"}

# The section of RFC 9110 that says so for each alias.
CODING_ALIAS_SECTIONS = {"x-gzip": "8.4.1.3", "x-compress": "8.4.1.1"}


def coding_acceptable(
    accept_encoding: List[Tuple[str, ParamDictType]], coding: str, wildcard: bool = True
) -> bool:
    """
    Whether a request's parsed Accept-Encoding allows ``coding`` (RFC 9110 Section 12.5.3):
    an explicit entry decides, then ``*`` (unless ``wildcard`` is False), and q=0 means not
    acceptable. An invalid q is treated as absent. ``x-gzip`` and ``x-compress`` are equivalent
    to ``gzip`` and ``compress``, both in the request and as ``coding``. An entry for the
    literal ``coding`` decides first (the first of any duplicates); an alias entry is used
    only when there is none.
    """
    explicit: Dict[str, Optional[float]] = {}
    aliased: Dict[str, Optional[float]] = {}
    for entry_coding, params in accept_encoding:
        q_value = parse_qvalue(dict(params), None)
        explicit.setdefault(entry_coding, q_value)
        aliased.setdefault(CODING_ALIASES.get(entry_coding, entry_coding), q_value)
    if coding in explicit:
        return explicit[coding] != 0.0
    canonical = CODING_ALIASES.get(coding, coding)
    if canonical in aliased:
        return aliased[canonical] != 0.0
    if wildcard and "*" in explicit:
        return explicit["*"] != 0.0
    return False


class CODING_ALIAS_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(coding)s' content-coding is a deprecated alias for '%(standard)s'."
    _text = """\
The
[IANA HTTP Content Coding Registry](https://www.iana.org/assignments/http-parameters/http-parameters.xhtml#content-coding)
lists `%(coding)s` as deprecated, as an alias for `%(standard)s`.

[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-%(section)s) says that a recipient
SHOULD consider `%(coding)s` to be equivalent to `%(standard)s`, so recipients are likely to
handle it; however, senders should use `%(standard)s`."""


def note_deprecated_codings(
    codings: Iterable[str], add_note: AddNoteMethodType, category: Optional[categories] = None
) -> None:
    """
    Add CODING_ALIAS_DEPRECATED once for each of ``x-gzip`` and ``x-compress`` that is in
    ``codings`` (already lower-cased), however many times it appears.
    """
    present = set(codings)
    for alias, standard in CODING_ALIASES.items():
        if alias in present:
            add_note(
                CODING_ALIAS_DEPRECATED,
                coding=alias,
                standard=standard,
                section=CODING_ALIAS_SECTIONS[alias],
                category=category,
            )
