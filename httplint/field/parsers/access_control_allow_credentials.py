from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.field import BAD_SYNTAX
from httplint.types import AddNoteMethodType


class access_control_allow_credentials(SingletonField):
    canonical_name = "Access-Control-Allow-Credentials"
    description = """\
The `Access-Control-Allow-Credentials` response header tells browsers whether to expose the response
to frontend code when the request's credentials mode (`Request.credentials`) is
`include`."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-credentials"
    syntax = "(?-i:true)"
    category = categories.SECURITY
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if field_value == "true":
            return "true"
        raise ValueError("Invalid value for Access-Control-Allow-Credentials")


class AccessControlAllowCredentialsTest(FieldTest):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"true"]
    expected_out = "true"


class AccessControlAllowCredentialsTestFalse(FieldTest):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"false"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]


class AccessControlAllowCredentialsTestTruethy(FieldTest):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"truethy"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]


class AccessControlAllowCredentialsTestCapTrue(FieldTest):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"True"]
    expected_out = None
    expected_notes = [BAD_SYNTAX]
