from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field import FIELD_DEPRECATED


class access_control(SingletonField):
    canonical_name = "Access-Control"
    description = """\
The `Access-Control` header was an experimental header for controlling access to resources. It is
obsolete and should not be used."""
    reference = "https://www.w3.org/TR/2007/WD-access-control-20071126/#access-control0"
    syntax = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True


class AccessControlTest(FieldTest):
    name = "Access-Control"
    inputs = [b"foo"]
    expected_out = "foo"
    expected_notes = [FIELD_DEPRECATED]
