from functools import partial
import re
from typing import TYPE_CHECKING, Any

from httplint.field import HttpField, BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.utils import RE_FLAGS, split_list_field
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class HttpListField(HttpField):
    """
    A HTTP field that allows multiple values, separated by commas.
    """

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string representing one value (after comma splitting), parse and return the result."""
        return field_value

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        values = split_list_field(field_value)
        i = 0
        for value in values:
            offset_add_note = partial(
                self.message.notes.add,
                f"offset-{offset}",
                field_name=self.canonical_name,
            )
            i += 1
            if self.syntax:
                element_syntax = (
                    self.syntax.element
                    if isinstance(self.syntax, rfc9110.list_rule)
                    else self.syntax
                )
                if not re.match(rf"^\s*(?:{element_syntax})\s*$", value, RE_FLAGS):
                    match = re.match(rf"^\s*(?:{element_syntax})", value, RE_FLAGS)
                    if match:
                        bad_char_index = match.end()
                        context_start = max(0, bad_char_index - 20)
                        context_end = min(len(value), bad_char_index + 20)
                        context = value[context_start:context_end]
                        pointer = " " * (bad_char_index - context_start) + "^"
                        problem = (
                            f"The invalid character '{value[bad_char_index]}' "
                            f"was found at position {bad_char_index + 1}:"
                            f"\n\n    {context}\n    {pointer}"
                        )
                        offset_add_note(
                            BAD_SYNTAX_DETAILED,
                            ref_uri=self.reference,
                            value=value,
                            problem=problem,
                            category=self.category,
                        )
                    else:
                        if self.report_syntax:
                            offset_add_note(
                                BAD_SYNTAX, ref_uri=self.reference, category=self.category
                            )
            try:
                parsed_value = self.parse(value.strip(), offset_add_note)
            except ValueError:
                continue
            self.value.append(parsed_value)
