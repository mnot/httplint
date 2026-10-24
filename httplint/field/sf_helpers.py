"""
Structured Field parameter and item checks, and number type tests that treat bools as non-numbers.
"""

from typing import Any, Dict, List, Type

from http_sf import Token

from httplint.note import MarkdownSafe, Note
from httplint.types import AddNoteMethodType
from httplint.util import inline_safe


def check_sf_params(
    params: Dict[str, Any],
    known_params: Dict[str, Dict[str, Any]],
    add_note: AddNoteMethodType,
    unknown_param_note: Type[Note],
    bad_param_val_note: Type[Note],
) -> str:
    """
    Format parameters for a clause, checking validity against known_params.

    Parameter names come from Structured Field dictionary-key syntax
    ([a-z0-9_.*-]) and are safe to embed directly. Parameter values are
    HTTP input; each is passed through inline_safe (no backticks or line
    breaks) and then always re-wrapped in a
    code span before being embedded here -- including into a known
    param's "desc" template, regardless of whether that template already
    puts `%s` in a span of its own -- so a value can never land in bare
    prose no matter how the template is written. The caller must wrap the
    assembled, now-safe result in MarkdownSafe.
    """
    param_list = []
    for param_name, param_value in params.items():
        safe_value = inline_safe(str(param_value))
        # An empty code span would swallow the next span's delimiters.
        shown_value = f"`{safe_value}`" if safe_value else "(empty)"
        # The notes below put %(value)s in a code span of their own, and an empty value would
        # leave an empty one, so they get a placeholder instead.
        note_value = param_value if str(param_value) else MarkdownSafe("(empty)")
        if param_name not in known_params:
            add_note(unknown_param_note, param=param_name)
            param_list.append(f"* `{param_name}`: {shown_value}")
        else:
            expected_type = known_params[param_name].get("type")
            if expected_type and not sf_type_matches(param_value, expected_type):
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=note_value,
                )
                param_list.append(f"* `{param_name}`: {shown_value}")
                continue

            allowed_values = known_params[param_name].get("values")
            if allowed_values and param_value not in allowed_values:
                add_note(
                    bad_param_val_note,
                    param=param_name,
                    value=note_value,
                )
                param_list.append(f"* `{param_name}`: {shown_value}")
                continue

            if "value_desc" in known_params[param_name]:
                desc = known_params[param_name]["value_desc"].get(param_value)
                if desc:
                    param_list.append(f"* {desc}")
                else:
                    param_list.append(f"* `{param_name}`: {shown_value}")
            elif "desc" in known_params[param_name]:
                desc = known_params[param_name]["desc"]
                if "%s" in desc:
                    wrapped = f"`{safe_value}`" if safe_value else "(empty)"
                    param_list.append(f"* {desc % wrapped}")
                elif param_value:
                    # A static desc with no %s is a flag-style description,
                    # meant for a truthy value; a falsy one (e.g. hit=?0)
                    # has nothing to report.
                    param_list.append(f"* {desc}")
            else:
                if param_value is True:
                    param_list.append(f"* `{param_name}`")
                else:
                    param_list.append(f"* `{param_name}`: {shown_value}")

    return "\n".join(param_list)


def check_sf_item_token(
    field_value: Any,
    valid_tokens: List[Token],
    add_note: AddNoteMethodType,
    valid_note: Type[Note],
    invalid_note: Type[Note],
    **kwargs: Any,
) -> None:
    """
    Check if a Structured Field Item is a Token and one of the valid tokens.
    """
    if isinstance(field_value, tuple):
        val = field_value[0]
        if isinstance(val, Token):
            if val in valid_tokens:
                add_note(valid_note, value=val, **kwargs)
            else:
                add_note(invalid_note, value=val, **kwargs)
        else:
            add_note(invalid_note, value=val, **kwargs)
    else:
        add_note(invalid_note, value=field_value, **kwargs)


def is_integer(value: Any) -> bool:
    "True if `value` is an integer. Python's bool is an int subclass, but JSON and SF's aren't."
    return isinstance(value, int) and not isinstance(value, bool)


def sf_type_matches(value: Any, expected: Any) -> bool:
    "isinstance(), except that a bool only matches if bool itself is expected."
    types = expected if isinstance(expected, tuple) else (expected,)
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def is_number(value: Any) -> bool:
    "True if `value` is an int or a float, but not a bool."
    return isinstance(value, (int, float)) and not isinstance(value, bool)
