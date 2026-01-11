from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class authorization(SingletonField):
    canonical_name = "Authorization"
    description = """\
The `Authorization` header field allows a user agent to authenticate itself with an origin server
-- usually, but not necessarily, after receiving a 401 (Unauthorized) response."""
    reference = f"{rfc9110.SPEC_URL}#field.authorization"
    syntax = rfc9110.Authorization
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class AuthorizationTest(FieldTest):
    name = "Authorization"
    inputs = [b"Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="]
    expected_out = "Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="
