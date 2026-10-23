from httplint.field.date_field import HttpDateField
from httplint.field.tests import FieldTest
from httplint.field.utils import BAD_DATE_SYNTAX
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
