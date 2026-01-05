from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class host(SingletonField):
    canonical_name = "Host"
    description = """\
The `Host` header field provides the host and port information from the target URI, enabling the
origin server to distinguish between resources while servicing requests for multiple host names on
a single IP address."""
    reference = f"{rfc9110.SPEC_URL}#field.host"
    syntax = rfc9110.Host
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class HostTest(FieldTest):
    name = "Host"
    inputs = [b"www.example.org"]
    expected_out = "www.example.org"
