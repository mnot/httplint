from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110



class content_location(HttpField):
    canonical_name = "Content-Location"
    description = """\
The `Content-Location` response header can used to supply an address for the
representation when it is accessible from a location separate from the request
URI."""
    reference = f"{rfc9110.SPEC_URL}#field.content-location"
    syntax = rfc9110.Content_Location
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True


class ContentLocationTest(FieldTest):
    name = "Content-Location"
    inputs = [b"/foo"]
    expected_out = "/foo"
