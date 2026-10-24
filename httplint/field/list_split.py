"""
Splitting a #rule list field value on commas.
"""

import re
from typing import FrozenSet, List

from httplint.field.common import RE_FLAGS
from httplint.syntax import rfc5234, rfc9110


def _char_set(pattern: str) -> FrozenSet[str]:
    """
    The characters below U+0100 that a single-character regex accepts. That covers
    everything qdtext and quoted-pair allow (they stop at obs-text, U+00FF). Under
    IGNORECASE the regex also accepts a few higher characters that case-fold into that
    range (U+0130, for one); field values are decoded as ASCII or ISO-8859-1, so none
    can occur.
    """
    return frozenset(c for c in map(chr, range(256)) if re.fullmatch(pattern, c, RE_FLAGS))


_QDTEXT = _char_set(rfc9110.qdtext)
_QUOTED_PAIR_CHAR = _char_set(
    rf"(?: {rfc5234.HTAB} | {rfc5234.SP} | {rfc5234.VCHAR} | {rfc9110.obs_text} )"
)


def split_list_field(
    field_value: str, angle_targets: bool = False, comments: bool = False
) -> List[str]:
    """
    Split a field value on commas, as the #rule needs.

    Commas inside a quoted-string don't split. A quote that doesn't start a valid
    quoted-string is an ordinary character of its item, so the malformed item reaches the
    field's own syntax check instead of being dropped.

    With ``angle_targets``, a ``<...>`` at the start of an item (as in Link) is skipped
    over whole, so commas inside it don't split either. It ends at the first ``>``; if there
    is none, or another ``<`` comes first, the ``<`` is an ordinary character. That last
    rule departs from RFC 8288 Appendix B.2, which takes the target up to the first ``>``:
    ``<a<b,c>`` is two (invalid) items here, not one. The target isn't a valid
    URI-Reference either way, and this keeps ``<a, <b>`` as two items, as before.

    With `comments`, commas inside a parenthesised comment (nested to any depth) don't
    split either; an unmatched "(" is an ordinary character, as with a stray quote.
    ``angle_targets`` has no effect with ``comments``; no field uses both.

    This is linear; an earlier regex-based version backtracked quadratically.
    """
    size = len(field_value)
    # quote_end[idx]: if inside a quoted-string at idx, the index just after its closing
    # quote, or -1 if it is unterminated or malformed.
    quote_end = [-1] * (size + 2)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == '"':
            quote_end[idx] = idx + 1
        elif char in _QDTEXT:
            quote_end[idx] = quote_end[idx + 1]
        elif char == "\\" and idx + 1 < size and field_value[idx + 1] in _QUOTED_PAIR_CHAR:
            quote_end[idx] = quote_end[idx + 2]
    if comments:
        return _split_outside_comments(field_value, quote_end)
    # run_end[idx]: where the run of non-comma characters and quoted-strings starting at
    # idx stops (at a comma or the end).
    run_end = [size] * (size + 1)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == '"':
            after = quote_end[idx + 1]
            run_end[idx] = run_end[after if after >= 0 else idx + 1]
        else:
            run_end[idx] = idx if char == "," else run_end[idx + 1]
    items: List[str] = []
    pos = 0
    # close: the first ">" after the last "<" we looked at; -1 if there is none, -2 if unset.
    # Reusing it is safe: it was the first ">" at or after an earlier "<", so while
    # close >= start (and start only moves forward) no ">" lies between start and close.
    # With no ">" at all (-1), nothing later can be a bracketed target. Searching every
    # time would be quadratic.
    close = -2
    while pos < size:
        stop = run_end[pos]
        if angle_targets and close != -1:
            start = pos
            while start < size and field_value[start].isspace():
                start += 1
            if start < size and field_value[start] == "<":
                if close < start:
                    close = field_value.find(">", start)
                if close != -1 and field_value.find("<", start + 1, close) == -1:
                    stop = run_end[close + 1]
        item = field_value[pos:stop].strip()
        if item:
            items.append(item)
        pos = stop + 1
    return items


def _split_outside_comments(field_value: str, quote_end: List[int]) -> List[str]:
    """
    Split on commas outside quoted-strings (per `quote_end`, see `split_list_field`) and
    comments. Comments nest, and a quoted-pair inside one can escape a parenthesis; a "(" with
    no matching ")" is an ordinary character.

    Linear: `after_comment` is filled right to left in one pass, then the value is scanned once.
    """
    size = len(field_value)
    # after_comment[idx]: scanning from idx inside a comment (one level deep), the index just
    # after the ")" that closes it, or -1 if there is none. A comment's end, for the "(" at
    # idx, is after_comment[idx + 1].
    after_comment = [-1] * (size + 2)
    for idx in range(size - 1, -1, -1):
        char = field_value[idx]
        if char == ")":
            after_comment[idx] = idx + 1
        elif char == "(":
            # The nested comment ends at after_comment[idx + 1]; carry on from there.
            nested = after_comment[idx + 1]
            after_comment[idx] = after_comment[nested] if nested >= 0 else -1
        elif char == "\\" and idx + 1 < size and field_value[idx + 1] in _QUOTED_PAIR_CHAR:
            after_comment[idx] = after_comment[idx + 2]
        else:
            after_comment[idx] = after_comment[idx + 1]

    items: List[str] = []
    item_start = 0
    idx = 0
    while idx < size:
        char = field_value[idx]
        if char == ",":
            item = field_value[item_start:idx].strip()
            if item:
                items.append(item)
            item_start = idx + 1
            idx += 1
        elif char == '"':
            after = quote_end[idx + 1]
            idx = after if after >= 0 else idx + 1
        elif char == "(":
            after = after_comment[idx + 1]
            idx = after if after >= 0 else idx + 1
        else:
            idx += 1
    item = field_value[item_start:].strip()
    if item:
        items.append(item)
    return items
