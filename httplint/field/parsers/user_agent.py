from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class user_agent(HttpField):
    canonical_name = "User-Agent"
    description = """\
The `User-Agent` header field contains information about the user agent originating the request."""
    reference = f"{rfc9110.SPEC_URL}#field.user-agent"
    syntax = rfc9110.User_Agent
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class UserAgentTest(FieldTest):
    name = "User-Agent"
    inputs = [b"CERN-LineMode/2.15 libwww/2.17b3"]
    expected_out = "CERN-LineMode/2.15 libwww/2.17b3"
