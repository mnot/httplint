from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ResponseLinterProtocol,
)


class access_control_allow_credentials(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Access-Control-Allow-Credentials"
    description = """\
The `Access-Control-Allow-Credentials` response header tells browsers whether to expose the response
to frontend code when the request's credentials mode (`Request.credentials`) is
`include`."""
    reference = "https://fetch.spec.whatwg.org/#http-access-control-allow-credentials"
    syntax = "(?-i:true)"
    category = categories.CORS
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if field_value == "true":
            return "true"
        raise ValueError("Invalid value for Access-Control-Allow-Credentials")


class AccessControlAllowCredentialsTest(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"true"]
    expected_out = "true"


class AccessControlAllowCredentialsTestFalse(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"false"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class AccessControlAllowCredentialsTestTruethy(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"truethy"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class AccessControlAllowCredentialsTestCapTrue(FieldTest[ResponseLinterProtocol]):
    name = "Access-Control-Allow-Credentials"
    inputs = [b"True"]
    expected_out = None
    expected_notes: NoteClassListType = [BAD_SYNTAX]
