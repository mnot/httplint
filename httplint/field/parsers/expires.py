from httplint.field.date_field import HttpDateField
from httplint.field.tests import FieldTest
from httplint.field.utils import BAD_DATE_SYNTAX, DATE_OBSOLETE
from httplint.note import categories
from httplint.syntax import rfc9111
from httplint.types import NoteClassListType, ResponseLinterProtocol


class expires(HttpDateField[ResponseLinterProtocol]):
    canonical_name = "Expires"
    description = """\
The `Expires` response header gives a time after which the response is considered stale by
caches."""
    reference = f"{rfc9111.SPEC_URL}#field.expires"
    category = categories.CACHING
    deprecated = False


class BasicExpiresTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadExpiresTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"0"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class BlankExpiresTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b""]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class ExpiresYearBigTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"Fri, 31 Dec 9999 23:59:59 GMT"]
    expected_out = 253402300799


class ExpiresEpochTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"Thu, 01 Jan 1970 00:00:00 GMT"]
    expected_out = 0


class ExpiresYearZeroTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"Mon, 01 Jan 0000 00:00:00 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class ExpiresImpossibleTest(FieldTest[ResponseLinterProtocol]):
    name = "Expires"
    inputs = [b"Mon, 31 Feb 2011 25:61:61 GMT"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_DATE_SYNTAX]


class ExpiresTwoDigitYearPastTest(FieldTest[ResponseLinterProtocol]):
    "More than 50 years after the response time, so it's the most recent past year."

    name = "Expires"
    inputs = [b"Sunday, 06-Nov-94 08:49:37 GMT"]
    expected_out = 784111777  # 1994, not 2094
    expected_notes: NoteClassListType = [DATE_OBSOLETE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 2_000_000_000.0  # 2033


class ExpiresTwoDigitYearFutureTest(FieldTest[ResponseLinterProtocol]):
    "Within 50 years of the response time, so it's in the future."

    name = "Expires"
    inputs = [b"Sunday, 06-Nov-94 08:49:37 GMT"]
    expected_out = 3939871777  # 2094
    expected_notes: NoteClassListType = [DATE_OBSOLETE]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.start_time = 3_000_000_000.0  # 2065
