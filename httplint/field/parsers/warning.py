from httplint.field import HttpField
from httplint.field.notes import FIELD_DEPRECATED
from httplint.field.tests import FieldTest
from httplint.syntax import rfc7234


class warning(HttpField):
    canonical_name = "Warning"
    description = """\
The `Warning` response header was used to carry additional information about the status or
transformation of a message that might not be reflected in it. It has been deprecated."""
    reference = f"{rfc7234.SPEC_URL}#header.warning"
    syntax = rfc7234.Warning_
    list_header = True
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True


class WarningTest(FieldTest):
    name = "Warning"
    inputs = [b'110 - "Response is stale"', b'299 - "Miscellaneous warning"']
    expected_out = ['110 - "Response is stale"', '299 - "Miscellaneous warning"']
    expected_notes = [FIELD_DEPRECATED]
