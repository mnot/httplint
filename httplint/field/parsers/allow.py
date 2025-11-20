from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110


class allow(HttpField):
    canonical_name = "Allow"
    description = """\
The `Allow` response header advertises the set of methods that are supported by the resource."""
    reference = f"{rfc9110.SPEC_URL}#field.allow"
    syntax = rfc9110.Allow
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class AllowTest(FieldTest):
    name = "Allow"
    inputs = [b"GET, POST"]
    expected_out = ["GET", "POST"]
