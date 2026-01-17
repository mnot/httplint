from httplint.field.list_field import HttpListField
from httplint.types import AddNoteMethodType
from httplint.note import categories


class tcn(HttpListField):
    canonical_name = "TCN"
    description = """\
The `TCN` response header is part of an experimental transparent content negotiation scheme. It
is not widely supported in clients.
"""
    reference = "https://www.rfc-editor.org/rfc/rfc2295"
    syntax = False
    category = categories.CONNEG
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        from httplint.field.unnecessary import (  # pylint: disable=import-outside-toplevel
            UNNECESSARY_HEADER,
        )

        add_note(UNNECESSARY_HEADER, header_name=self.wire_name)
        return field_value
