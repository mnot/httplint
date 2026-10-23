from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import NoteClassListType, ResponseLinterProtocol


class retry_after(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Retry-After"
    description = """\
The `Retry-After` response header can be used with a `503` (Service Unavailable) response to
indicate how long the service is expected to be unavailable to the requesting client.

The value of this field can be either a date or an integer number of seconds."""
    reference = f"{rfc9110.SPEC_URL}#field.retry-after"
    syntax = rfc9110.Retry_After
    deprecated = False


class RetryAfterDateTest(FieldTest[ResponseLinterProtocol]):
    name = "Retry-After"
    inputs = [b"Sat, 29 Oct 1994 19:43:31 GMT"]
    expected_out = "Sat, 29 Oct 1994 19:43:31 GMT"


class RetryAfterSecondsTest(FieldTest[ResponseLinterProtocol]):
    name = "Retry-After"
    inputs = [b"120"]
    expected_out = "120"


class RetryAfterLowerCaseDateTest(FieldTest[ResponseLinterProtocol]):
    "The day name, month and GMT are case-sensitive."

    name = "Retry-After"
    inputs = [b"sat, 29 oct 1994 19:43:31 gmt"]
    expected_out = "sat, 29 oct 1994 19:43:31 gmt"
    expected_notes: NoteClassListType = [BAD_SYNTAX]
