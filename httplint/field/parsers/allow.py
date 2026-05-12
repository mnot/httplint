from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import (
    ResponseLinterProtocol,
)


class allow(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Allow"
    description = """\
The `Allow` response header advertises the set of methods that are supported by the resource."""
    reference = f"{rfc9110.SPEC_URL}#field.allow"
    syntax = rfc9110.Allow
    deprecated = False


class AllowTest(FieldTest[ResponseLinterProtocol]):
    name = "Allow"
    inputs = [b"GET, POST"]
    expected_out = ["GET", "POST"]
