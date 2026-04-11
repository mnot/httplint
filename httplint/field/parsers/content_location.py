from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import (
    ResponseLinterProtocol,
)


class content_location(SingletonField[ResponseLinterProtocol]):
    canonical_name = "Content-Location"
    description = """\
The `Content-Location` response header can used to supply an address for the
representation when it is accessible from a location separate from the request
URI."""
    reference = f"{rfc9110.SPEC_URL}#field.content-location"
    syntax = rfc9110.Content_Location
    deprecated = False


class ContentLocationTest(FieldTest[ResponseLinterProtocol]):
    name = "Content-Location"
    inputs = [b"/foo"]
    expected_out = "/foo"
