import re
from typing import Any, TYPE_CHECKING

import http_sf

from httplint.field import HttpField
from httplint.field.notes import (
    DUPLICATE_KEY,
    STRUCTURED_FIELD_PARSE_ERROR,
)
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter

RE_FLAGS = re.VERBOSE | re.IGNORECASE


class StructuredField(HttpField):
    """
    A HTTP field that uses the Structured Fields encoding.
    See: RFC 8941
    """

    nonstandard_syntax = True
    structured_field = True
    sf_type: str = "item"  # item, list, dict

    def handle_input(self, field_value: str, add_note: AddNoteMethodType) -> None:
        self.value.append(field_value)

    def finish(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> None:
        combined_value = ", ".join(self.value).strip()
        parsed_value: Any = None

        def on_duplicate_key(key: str, context: str) -> None:
            add_note(DUPLICATE_KEY, key=key, context=context)

        try:
            if self.sf_type == "list":
                _, parsed_value = http_sf.parse_list(
                    combined_value.encode("utf-8"),
                    on_duplicate_key=on_duplicate_key,
                )
            elif self.sf_type == "dictionary":
                _, parsed_value = http_sf.parse_dictionary(
                    combined_value.encode("utf-8"),
                    on_duplicate_key=on_duplicate_key,
                )
            elif self.sf_type == "item":
                _, parsed_value = http_sf.parse_item(
                    combined_value.encode("utf-8"),
                    on_duplicate_key=on_duplicate_key,
                )
            else:
                raise ValueError(f"Unknown sf_type: {self.sf_type}")
            self.value = parsed_value
        except ValueError as why:
            add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
            self.value = None
        except Exception as why:  # pylint: disable=broad-except
            add_note(STRUCTURED_FIELD_PARSE_ERROR, error=f"{why}")
            self.value = None

        super().finish(message, add_note)
