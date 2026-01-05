from typing import cast, TYPE_CHECKING
from urllib.parse import urlparse

from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType
from httplint.note import Note, categories, levels

if TYPE_CHECKING:
    from httplint.message import HttpRequestLinter


class REFERER_SECURE_TO_INSECURE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "The Referer header is sent from a secure origin to an insecure target."
    _text = """\
HTTP prohibits a user agent from sending a Referer header field in an unsecured HTTP request
if the referring resource was accessed with a secure protocol.

See [RFC 9110 Section 10.1.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.1.3)
for details."""


class REFERER_SECURE_TO_DIFFERENT_ORIGIN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The Referer header is sent from a secure origin to a different origin."
    _text = """\
HTTP prohibits a user agent from sending a Referer header field if the referring resource was
accessed with a secure protocol and the request target has an origin differing from that of the
referring resource, unless the referring resource explicitly allows Referer to be sent.

See [RFC 9110 Section 10.1.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.1.3)
for details."""


class referer(SingletonField):
    canonical_name = "Referer"
    description = """\
The `Referer` [sic] header field allows the user agent to specify a URI Reference for the
resource from which the target URI was obtained (i.e., the "referrer")."""
    reference = f"{rfc9110.SPEC_URL}#field.referer"
    syntax = rfc9110.Referer
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if getattr(self.message, "message_type", None) != "request":
            return

        referer_uri = self.value
        request_uri = cast("HttpRequestLinter", self.message).uri

        if not referer_uri or not request_uri:
            return

        try:
            parsed_referer = urlparse(referer_uri)
            parsed_request = urlparse(request_uri)
        except ValueError:
            return  # Already handled by URI syntax checks

        if parsed_referer.scheme.lower() in ["https", "wss"]:
            if parsed_request.scheme.lower() in ["http", "ws"]:
                add_note(REFERER_SECURE_TO_INSECURE)

            referer_origin = (parsed_referer.scheme, parsed_referer.netloc)
            request_origin = (parsed_request.scheme, parsed_request.netloc)

            if referer_origin != request_origin:
                add_note(REFERER_SECURE_TO_DIFFERENT_ORIGIN)


class RefererTest(FieldTest):
    name = "Referer"
    inputs = [b"http://www.example.org/hypertext/Overview.html"]
    expected_out = "http://www.example.org/hypertext/Overview.html"
