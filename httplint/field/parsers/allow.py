from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110


class allow(HttpListField):
    canonical_name = "Allow"
    description = """\
The `Allow` response header advertises the set of methods that are supported by the resource."""
    reference = f"{rfc9110.SPEC_URL}#field.allow"
    syntax = rfc9110.Allow
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class AllowTest(FieldTest):
    name = "Allow"
    inputs = [b"GET, POST"]
    expected_out = ["GET", "POST"]
