from httplint.field.date_field import HttpDateField
from httplint.field.http_date import BAD_DATE_SYNTAX, DATE_OBSOLETE
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, RequestLinterProtocol


class if_modified_since(HttpDateField[RequestLinterProtocol]):
    canonical_name = "If-Modified-Since"
    description = """\
The `If-Modified-Since` header field makes a request method conditional on the
selected representation's modification date being more recent than the date provided in the
field-value."""
    reference = f"{rfc9110.SPEC_URL}#field.if-modified-since"
    deprecated = False


class IfModifiedSinceTest(FieldTest[RequestLinterProtocol]):
    name = "If-Modified-Since"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = 783459811


class IfModifiedSinceEpochTest(FieldTest[RequestLinterProtocol]):
    name = "If-Modified-Since"
    inputs = [b"Thu, 01 Jan 1970 00:00:00 GMT"]
    expected_out = 0


class IfModifiedSinceObsoleteTest(FieldTest[RequestLinterProtocol]):
    name = "If-Modified-Since"
    inputs = [b"Saturday, 29-Oct-94 19:43:31 GMT"]
    expected_out = 783459811
    expected_notes: NoteClassListType = [DATE_OBSOLETE]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.start_time = 1_000_000_000.0  # 2001; the two-digit year is resolved against it


class IfModifiedSinceBadTest(FieldTest[RequestLinterProtocol]):
    name = "If-Modified-Since"
    inputs = [b"yesterday"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]
