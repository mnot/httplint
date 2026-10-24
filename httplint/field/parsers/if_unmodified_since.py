from httplint.field.date_field import HttpDateField
from httplint.field.http_date import BAD_DATE_SYNTAX, DATE_OBSOLETE
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, RequestLinterProtocol


class if_unmodified_since(HttpDateField[RequestLinterProtocol]):
    canonical_name = "If-Unmodified-Since"
    description = """\
The `If-Unmodified-Since` header field makes the request method conditional on the selected
representation's last modification date being earlier than or equal to the date provided in the
field-value."""
    reference = f"{rfc9110.SPEC_URL}#field.if-unmodified-since"
    category = categories.VALIDATION
    deprecated = False


class IfUnmodifiedSinceTest(FieldTest[RequestLinterProtocol]):
    name = "If-Unmodified-Since"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = 783459811


class IfUnmodifiedSinceObsoleteTest(FieldTest[RequestLinterProtocol]):
    name = "If-Unmodified-Since"
    inputs = [b"Saturday, 29-Oct-94 19:43:31 GMT"]
    expected_out = 783459811
    expected_notes: NoteClassListType = [DATE_OBSOLETE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.start_time = 1_000_000_000.0  # 2001; the two-digit year is resolved against it


class IfUnmodifiedSinceBadTest(FieldTest[RequestLinterProtocol]):
    name = "If-Unmodified-Since"
    inputs = [b"yesterday"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]
