import re
from typing import Dict, Generic, List, Optional, Tuple, Union

from httplint.field import BAD_SYNTAX_DETAILED, HttpField
from httplint.field.singleton_field import SINGLE_HEADER_REPEAT
from httplint.field.utils import RE_FLAGS
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, TMessage
from httplint.util import invalid_char_problem, markdown_context

# A challenge or set of credentials: the auth-scheme, and either a token68 or a dictionary of
# auth-params. The scheme and param names are lowercased (both are case-insensitive), values
# are unquoted, and the first instance of a repeated name wins. The original spelling of the
# scheme is still available in the section's raw_fields.
Challenge = Tuple[str, Union[str, Dict[str, str]]]

_TOKEN_RE = re.compile(rfc9110.auth_scheme, RE_FLAGS)
_TOKEN68_RE = re.compile(rfc9110.token68, RE_FLAGS)
_AUTH_PARAM_RE = re.compile(
    rf"(?P<name> {rfc9110.token} ) {rfc9110.BWS} = {rfc9110.BWS} "
    rf"(?: (?P<token> {rfc9110.token} ) | (?P<quoted> {rfc9110.quoted_string} ) )",
    RE_FLAGS,
)
_AUTH_PARAM_START_RE = re.compile(
    rf"{rfc9110.token} {rfc9110.BWS} = {rfc9110.BWS}",
    RE_FLAGS,
)
_QUOTED_PAIR_RE = re.compile(r"\\(.)", re.DOTALL)
_OWS_CHARS = " \t"


def _skip(text: str, pos: int, chars: str) -> int:
    "Return the index of the first character at or after pos that isn't in chars."
    size = len(text)
    while pos < size and text[pos] in chars:
        pos += 1
    return pos


def _parse_params(text: str, pos: int, params: Dict[str, str]) -> Tuple[int, bool]:
    """
    Parse the auth-params of a challenge starting at ``pos``, just after the scheme and
    its SP. Returns where the challenge ends, and whether it ended cleanly (at a comma
    that doesn't continue it, or at the end of the text) rather than at a syntax error.
    """
    size = len(text)
    first = True
    while True:
        raw = pos
        pos = _skip(text, pos, _OWS_CHARS)
        if pos >= size:
            return pos, True
        if text[pos] == ",":
            ahead = _skip(text, pos, _OWS_CHARS + ",")
            param = _AUTH_PARAM_RE.match(text, ahead) if ahead < size else None
            if not param:
                return ahead, True  # a new challenge, or the end, follows
            pos = ahead
        elif first and pos == raw:  # only SP precedes the first auth-param
            param = _AUTH_PARAM_RE.match(text, pos)
        else:
            return pos, False
        if not param:
            # Blame the value if the name and "=" are fine (e.g. an unterminated quote).
            name_and_equals = _AUTH_PARAM_START_RE.match(text, pos)
            return (name_and_equals.end() if name_and_equals else pos), False
        first = False
        quoted = param.group("quoted")
        params.setdefault(
            param.group("name").lower(),
            (
                _QUOTED_PAIR_RE.sub(r"\1", quoted[1:-1])
                if quoted is not None
                else param.group("token")
            ),
        )
        pos = param.end()


def _skip_to_comma(text: str, pos: int) -> int:
    "Return the index of the next comma at or after pos that isn't inside a quoted-string."
    size = len(text)
    while pos < size:
        char = text[pos]
        if char == ",":
            return pos
        if char == '"':
            # An unterminated quote has no closing quote, so it swallows the rest of the text.
            pos += 1
            while pos < size and text[pos] != '"':
                pos += 2 if text[pos] == "\\" else 1
            if pos >= size:
                return size
        pos += 1
    return size


def _resync(text: str, error: int) -> int:
    """
    Where to resume parsing a list after a syntax error at ``error``: the start of the next
    element that isn't an auth-param. Auth-params after the error are leftovers of the
    broken challenge, so they are skipped rather than reported again.
    """
    size = len(text)
    pos = _skip_to_comma(text, error)
    while pos < size:
        pos = _skip(text, pos, _OWS_CHARS + ",")
        param = _AUTH_PARAM_RE.match(text, pos) if pos < size else None
        if not param:
            return pos
        pos = _skip_to_comma(text, param.end())
    return size


def _parse_run(
    text: str, pos: int, single: bool, challenges: List[Challenge], starts: List[int]
) -> Optional[int]:
    """
    Parse challenges from ``pos`` until the end of ``text`` or a syntax error, appending to
    ``challenges`` and ``starts``. Returns the index of the error, or None.
    """
    size = len(text)
    if single:
        if not text:
            return 0
    else:
        pos = _skip(text, pos, _OWS_CHARS + ",")
    while pos < size:
        scheme_match = _TOKEN_RE.match(text, pos)
        if not scheme_match:
            return pos
        starts.append(pos)
        scheme = scheme_match.group()
        pos = scheme_match.end()
        value: Union[str, Dict[str, str]] = {}
        clean = True

        if pos < size and text[pos] == " ":
            pos = _skip(text, pos, " ")
            token68 = _TOKEN68_RE.match(text, pos)
            after = _skip(text, token68.end(), _OWS_CHARS) if token68 else pos
            if token68 and (after >= size or text[after] == ","):
                value = token68.group()
                pos = after
            else:
                params: Dict[str, str] = {}
                value = params
                params_start = pos
                pos, clean = _parse_params(text, pos, params)
                if token68 and not clean and pos == params_start:
                    pos = after  # the token68 is fine; blame what follows it
        else:
            pos = _skip(text, pos, _OWS_CHARS)
            clean = pos >= size or text[pos] == ","

        if value or clean:
            challenges.append((scheme.lower(), value))
        else:
            starts.pop()
        if not clean:
            return pos
        if single:
            # Anything left is a comma after a token68 or bare scheme, or a second challenge.
            return pos if pos < size else None
        pos = _skip(text, pos, _OWS_CHARS + ",")
    return None


def parse_challenges(
    text: str, single: bool = False
) -> Tuple[List[Challenge], List[int], List[int]]:
    """
    Parse ``text`` as ``#challenge`` (RFC 9110 Section 11.6.1).

    If ``single`` is true, parse it as one ``credentials`` (Section 11.6.2) instead, which
    has the challenge grammar but isn't a list: it can't be empty, start with a comma, or
    have anything after the first element except empty elements in its auth-param list.

    Returns the challenges, the index at which each starts, and the index of each syntax
    error (none if the text is valid). A challenge containing an error is kept if it has a
    token68 or at least one auth-param.

    After an error in a list, parsing resumes at the next comma outside a quoted-string (see
    ``_resync``), so later challenges are still found and each defect gets its own error.
    Credentials stop at the first error.

    A challenge's auth-params are comma-separated, as are challenges, so a comma is
    followed by an auth-param (``token BWS "="``) if it continues the challenge, or by a
    new challenge otherwise. This is linear: each position is examined a bounded number
    of times, and none of the regexes can backtrack across a position.
    """
    challenges: List[Challenge] = []
    starts: List[int] = []
    errors: List[int] = []
    pos = 0
    while True:
        error = _parse_run(text, pos, single, challenges, starts)
        if error is None:
            break
        errors.append(error)
        pos = _resync(text, error)
        if single or pos >= len(text):
            break
    return challenges, starts, errors


def _parse_field_line(
    field: HttpField[TMessage], field_value: str, offset: int, single: bool = False
) -> List[Challenge]:
    """
    Parse one field line for ``field``, reporting each syntax error.
    """
    challenges, _, errors = parse_challenges(field_value, single)
    for error in errors:
        problem = invalid_char_problem(field_value, error)
        field.message.notes.add(
            f"offset-{offset}",
            BAD_SYNTAX_DETAILED,
            field_name=field.canonical_name,
            ref_uri=field.reference,
            value=field_value,
            problem=problem,
            context=markdown_context(field_value, error),
            category=field.category,
        )
    return challenges


class ChallengeField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field containing challenges (RFC 9110 Section 11.6.1), such as WWW-Authenticate.

    These aren't comma-separated lists: a challenge's auth-params are themselves separated
    by commas. The value is a list of ``(scheme, token68 | {param: value})`` tuples with the
    scheme lowercased; see ``parse_challenges``. The scheme's original spelling is in the
    section's ``raw_fields``.

    No scheme-specific checks are made here; subclasses can add them in ``evaluate``.
    """

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.value.extend(_parse_field_line(self, field_value, offset))


class CredentialsField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field containing credentials (RFC 9110 Section 11.6.2), such as Authorization.

    Credentials have the same grammar as a single challenge, but aren't a list, and the field
    can only occur once. The value is one ``(scheme, token68 | {param: value})`` tuple with
    the scheme lowercased (its original spelling is in the section's ``raw_fields``), or
    None if there is nothing usable.

    No scheme-specific checks are made here; subclasses can add them in ``evaluate``.
    """

    def __init__(self, wire_name: str, message: TMessage) -> None:
        super().__init__(wire_name, message)
        self.raw_values: List[Tuple[str, int]] = []

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        self.raw_values.append((field_value, offset))

    def finish(self, add_note: AddNoteMethodType) -> None:
        if not self.raw_values:
            self.value = None
            return
        if len(self.raw_values) > 1:
            add_note(SINGLE_HEADER_REPEAT)
        field_value, offset = self.raw_values[0]
        parsed = _parse_field_line(self, field_value.strip(), offset, single=True)
        self.value = parsed[0] if parsed else None
        if self.value is not None:
            self.evaluate(add_note)
