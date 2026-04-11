from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, RequestLinterProtocol


class user_agent(SingletonField[RequestLinterProtocol]):
    canonical_name = "User-Agent"
    description = """\
The `User-Agent` header field contains information about the user agent originating the request."""
    reference = f"{rfc9110.SPEC_URL}#field.user-agent"
    syntax = rfc9110.User_Agent
    deprecated = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class UserAgentTest(FieldTest[RequestLinterProtocol]):
    name = "User-Agent"
    inputs = [b"CERN-LineMode/2.15 libwww/2.17b3"]
    expected_out = "CERN-LineMode/2.15 libwww/2.17b3"
