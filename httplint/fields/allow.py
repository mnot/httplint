from httplint.fields import HttpField
from httplint.fields._test import FieldTest
from httplint.syntax import rfc7231


class allow(HttpField):
    canonical_name = "Allow"
    description = """\
The `Allow` header advertises the set of methods that are supported by the resource."""
    reference = f"{rfc7231.SPEC_URL}#header.allow"
    syntax = rfc7231.Allow
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class AllowTest(FieldTest):
    name = "Allow"
    inputs = [b"GET, POST"]
    expected_out = ["GET", "POST"]
