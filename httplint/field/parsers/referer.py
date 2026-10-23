from httplint.field import BAD_SYNTAX
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.field.utils import is_secure, resolve_url
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    RequestLinterProtocol,
)
from httplint.util import iri_to_uri


class referer(SingletonField[RequestLinterProtocol]):
    canonical_name = "Referer"
    description = """\
The `Referer` [sic] header field allows the user agent to specify a URI Reference for the
resource from which the target URI was obtained (i.e., the "referrer")."""
    reference = f"{rfc9110.SPEC_URL}#field.referer"
    syntax = rfc9110.Referer
    deprecated = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        bad_uri = False
        try:
            bad_uri = resolve_url(iri_to_uri(field_value)) is None
        except UnicodeError:
            pass  # IDNA problems aren't reported here
        except ValueError:
            bad_uri = True
        if bad_uri:
            add_note(REFERER_BAD_URI, uri=field_value)
            self.suppress_syntax_note()
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if getattr(self.message, "message_type", None) != "request":
            return

        referer_uri = self.value
        request_uri = self.message.uri

        if not referer_uri or not request_uri:
            return

        try:
            # Compare like with like: the request's URI has been through iri_to_uri
            referer_uri = iri_to_uri(referer_uri)
        except (ValueError, UnicodeError):
            return  # reported by parse()
        parsed_referer = resolve_url(referer_uri)
        parsed_request = resolve_url(request_uri)
        if parsed_referer is None or parsed_request is None:
            return  # reported by parse(), or a bad request URI

        if is_secure(parsed_referer):
            if parsed_request.scheme.lower() in ["http", "ws"]:
                add_note(REFERER_SECURE_TO_INSECURE)

            referer_origin = (parsed_referer.scheme, parsed_referer.netloc)
            request_origin = (parsed_request.scheme, parsed_request.netloc)

            if referer_origin != request_origin:
                add_note(REFERER_SECURE_TO_DIFFERENT_ORIGIN)


class REFERER_BAD_URI(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Referer header isn't a valid URI."
    _text = """\
The `Referer` header's value, `%(uri)s`, can't be parsed as a URI (for example, it may have a
malformed IP address in its host), so recipients can't make use of it."""


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


class RefererTest(FieldTest[RequestLinterProtocol]):
    name = "Referer"
    inputs = [b"http://www.example.org/hypertext/Overview.html"]
    expected_out = "http://www.example.org/hypertext/Overview.html"


class RefererQueryTest(FieldTest[RequestLinterProtocol]):
    name = "Referer"
    inputs = [b"/a?b=c"]
    expected_out = "/a?b=c"


class RefererColonSegmentTest(FieldTest[RequestLinterProtocol]):
    name = "Referer"
    inputs = [b"1:2"]
    expected_out = "1:2"
    expected_notes: NoteClassListType = [BAD_SYNTAX]


class RefererBadURITest(FieldTest[RequestLinterProtocol]):
    name = "Referer"
    inputs = [b"https://[::1"]
    expected_out = "https://[::1"
    expected_notes: NoteClassListType = [REFERER_BAD_URI]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.uri = "http://example.com/"


class RefererBadSyntaxTest(FieldTest[RequestLinterProtocol]):
    "A syntax error that isn't an unresolvable URI is still BAD_SYNTAX."

    name = "Referer"
    inputs = [b"http://example.com/a b"]
    expected_out = "http://example.com/a b"
    expected_notes: NoteClassListType = [BAD_SYNTAX]

    def set_request_context(self, message: RequestLinterProtocol) -> None:
        message.uri = "http://example.com/"
