from httplint.field import FIELD_DEPRECATED
from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9111
from httplint.types import NoteClassListType, ResponseLinterProtocol


class warning(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Warning"
    description = """\
The `Warning` response header was used to carry additional information about the status or
transformation of a message that might not be reflected in it. It has been deprecated."""
    reference = f"{rfc9111.SPEC_URL}#field.warning"
    syntax = rfc9111.Warning_
    category = categories.CACHING
    deprecated = True


class WarningTest(FieldTest[ResponseLinterProtocol]):
    name = "Warning"
    inputs = [b'110 - "Response is stale"', b'299 - "Miscellaneous warning"']
    expected_out = ['110 - "Response is stale"', '299 - "Miscellaneous warning"']
    expected_notes: NoteClassListType = [FIELD_DEPRECATED]
