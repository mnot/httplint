from functools import partial
from typing import Any, Generic, List, Union

from httplint.field import HttpField
from httplint.field.utils import split_list_field
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, TMessage


class HttpListField(HttpField[TMessage], Generic[TMessage]):
    """
    A HTTP field that allows multiple values, separated by commas.
    """

    @classmethod
    def _syntax_source(cls) -> Union[str, rfc9110.list_rule, bool]:
        "Each list element is checked on its own."
        if isinstance(cls.syntax, rfc9110.list_rule):
            return cls.syntax.element
        return cls.syntax

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string representing one value (after comma splitting), parse and return the result.
        Raise ValueError if parsing fails.
        """
        return field_value

    def split_values(self, field_value: str) -> List[str]:
        "Split a field line into list elements; fields with unusual delimiters can override."
        return split_list_field(field_value)

    def handle_input(self, field_value: str, add_note: AddNoteMethodType, offset: int) -> None:
        for value in self.split_values(field_value):
            offset_add_note = partial(
                self.message.notes.add,
                f"offset-{offset}",
                field_name=self.canonical_name,
            )
            try:
                with self._syntax_checked(value, offset_add_note):
                    parsed_value = self.parse(value.strip(), offset_add_note)
            except ValueError:
                continue
            self.value.append(parsed_value)
