from typing import Generic

from httplint.field.http_date import parse_http_date
from httplint.field.singleton_field import SingletonField
from httplint.types import AddNoteMethodType, TMessage


class HttpDateField(SingletonField[TMessage], Generic[TMessage]):
    """
    A HTTP field whose value is a single HTTP-date.

    The value is the date as seconds since the epoch, which can be 0; subclasses
    should test it with ``is not None``, not for truthiness.
    """

    syntax = False  # parse_http_date does its own syntax check and notes

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        return parse_http_date(
            field_value, add_note, category=self.category, now=self.message.start_time
        )
