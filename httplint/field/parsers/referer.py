from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class referer(HttpField):
    canonical_name = "Referer"
    description = """\
The `Referer` [sic] header field allows the user agent to specify a URI Reference for the
resource from which the target URI was obtained (i.e., the "referrer")."""
    reference = f"{rfc9110.SPEC_URL}#field.referer"
    syntax = rfc9110.Referer
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        pass


class RefererTest(FieldTest):
    name = "Referer"
    inputs = [b"http://www.example.org/hypertext/Overview.html"]
    expected_out = "http://www.example.org/hypertext/Overview.html"
