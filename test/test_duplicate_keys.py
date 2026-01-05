from http_sf import Token
from httplint.field.tests import FieldTest
from httplint.field.structured_field import DUPLICATE_KEY
from httplint.field.parsers.permissions_policy import PERMISSIONS_POLICY_INVALID_VALUE, PERMISSIONS_POLICY_PRESENT
from httplint.field.parsers.proxy_status import PROXY_STATUS

class DuplicateKeyDictionaryTest(FieldTest):
    name = "Permissions-Policy"
    inputs = [b"geolocation=(), geolocation=()"]
    expected_out = {"geolocation": ([], {})}
    expected_notes = [DUPLICATE_KEY, PERMISSIONS_POLICY_PRESENT]

class DuplicateKeyParameterTest(FieldTest):
    name = "Proxy-Status"
    inputs = [b"ExampleProxy; error=http_protocol_error; error=dns_error"]
    expected_out = [(Token("ExampleProxy"), {"error": Token("dns_error")})]
    expected_notes = [DUPLICATE_KEY, PROXY_STATUS]


if __name__ == "__main__":
    import unittest
    unittest.main()
