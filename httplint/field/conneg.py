"""
Content negotiation helpers: q-values and Vary coverage.
"""

import re
from typing import Any, Optional

from httplint.field.common import RE_FLAGS
from httplint.field.params import split_params
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType


class BAD_Q_VALUE(Note):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "The q value on '%(item)s' is invalid."
    _text = """\
The `q` parameter must be a decimal number between 0 and 1, with at most 3 digits after the
decimal point (for example, `0.5`). A sign, an exponent, quotes, or a missing leading digit
aren't allowed."""


def _q_is_quoted(raw_params: str) -> bool:
    "Is the first q parameter in ``raw_params`` a quoted-string?"
    for segment in split_params(raw_params):
        name, _, value = segment.partition("=")
        if name.lower() == "q":
            return value.startswith('"')
    return False


def parse_qvalue(
    params: ParamDictType,
    add_note: Optional[AddNoteMethodType],
    raw_params: str = "",
    **note_vars: Any,
) -> Optional[float]:
    """
    Remove the ``q`` parameter from ``params`` and return it as a float, or None if it
    is absent or invalid.

    The value must match ``rfc9110.qvalue``. An invalid value is reported with
    ``BAD_Q_VALUE`` (passing ``note_vars`` to it, which should include ``item``), unless
    ``add_note`` is None; use that where the field's syntax check has already flagged it.

    ``parse_params`` unquotes values, but a q-value can't be a quoted-string; pass the
    parameter text as ``raw_params`` to have that detected too.
    """
    if "q" not in params:
        return None
    q_str = params.pop("q")
    if (
        q_str is not None
        and not _q_is_quoted(raw_params)
        and re.fullmatch(rfc9110.qvalue, q_str, RE_FLAGS)
    ):
        return float(q_str)
    if add_note is not None:
        add_note(BAD_Q_VALUE, **note_vars)
    return None


def vary_covers(message: Any, name: str) -> bool:
    """
    Does the message's Vary header cover the request header ``name``? That is the case
    if it lists the name (case-insensitively) or is ``*``.

    Callers check cacheability first, and ``Vary: *`` makes a response uncacheable, so the
    ``*`` branch is rarely reached; it keeps the helper correct for callers that don't.
    """
    vary_values = message.headers.parsed.get("vary") or ()
    values = {str(v).lower() for v in vary_values}
    return "*" in values or name.lower() in values
