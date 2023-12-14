from typing import Optional

from httplint.field.finder import HttpFieldFinder
from httplint.message import HttpMessageLinter

_linter = HttpMessageLinter()


def get_field_description(field_name: str) -> Optional[str]:
    """Return the description for the named field, or None if not found."""
    handler_class = HttpFieldFinder.find_handler_class(field_name)
    if handler_class is not None:
        return handler_class(field_name, _linter).description
    return None
