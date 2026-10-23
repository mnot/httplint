from typing import Any

from http_sf import Token

from httplint.field.tests import FieldTest
from httplint.field.token_policy_field import TokenPolicyField
from httplint.note import Note, categories, levels
from httplint.types import NoteClassListType, ResponseLinterProtocol


class COEP_REQUIRE_CORP(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response requires resources to have a CORP header%(report_only)s."
    _text = """\
The `require-corp`
[Cross Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
requires that all cross-origin resources must explicitly grant permission to be loaded via a
`Cross-Origin-Resource-Policy` header, in supporting browsers.%(report_only_text)s"""


class COEP_CREDENTIALLESS(Note):
    category = categories.SECURITY
    level = levels.GOOD
    _summary = "This response loads cross-origin resources without credentials%(report_only)s."
    _text = """\
The `credentialless`
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
allows loading cross-origin resources without explicit permission in supporting browsers, but
requests for them will not include credentials (cookies, client certificates,
etc.).%(report_only_text)s"""


class COEP_UNSAFE_NONE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "This response allows loading cross-origin resources without restriction%(report_only)s."
    )
    _text = """\
The `unsafe-none`
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
is the default behavior, allowing cross-origin resources to be loaded
without explicit permission in supporting browsers.

This does not provide cross-origin isolation.%(report_only_text)s"""


class CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.BAD
    _summary = "This response's %(field_name)s has an invalid value."
    _text = """\
The `%(field_name)s` header must be one of `require-corp`, `credentialless`, or
`unsafe-none`.
"""


class COEP_REPORT_TO_MISSING(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The report-to endpoint '%(endpoint)s' is not defined%(report_only)s."
    _text = """\
The `report-to` parameter in the
[Cross-Origin Embedder Policy](https://fetch.spec.whatwg.org/#cross-origin-embedder-policy-header)
header specifies a reporting endpoint, but no matching endpoint refers to it in the
`Reporting-Endpoints` header."""


class cross_origin_embedder_policy(TokenPolicyField):
    canonical_name = "Cross-Origin-Embedder-Policy"
    description = """\
The `Cross-Origin-Embedder-Policy` header field prevents a document from loading any cross-origin
resources that don't explicitly grant the document permission (using CORP or CORS)."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coep"
    policy_notes = {
        "require-corp": COEP_REQUIRE_CORP,
        "credentialless": COEP_CREDENTIALLESS,
        "unsafe-none": COEP_UNSAFE_NONE,
    }
    bad_value_note = CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE
    report_to_missing_note = COEP_REPORT_TO_MISSING


class CrossOriginEmbedderPolicyRequireCorpTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp"]
    expected_out: Any = (Token("require-corp"), {})
    expected_notes: NoteClassListType = [COEP_REQUIRE_CORP]


class CrossOriginEmbedderPolicyCredentiallessTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"credentialless"]
    expected_out: Any = (Token("credentialless"), {})
    expected_notes: NoteClassListType = [COEP_CREDENTIALLESS]


class CrossOriginEmbedderPolicyUnsafeNoneTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"unsafe-none"]
    expected_out: Any = (Token("unsafe-none"), {})
    expected_notes: NoteClassListType = [COEP_UNSAFE_NONE]


class CrossOriginEmbedderPolicyBadValueTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"foo"]
    expected_out: Any = (Token("foo"), {})
    expected_notes: NoteClassListType = [CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE]


class CrossOriginEmbedderPolicyReportToTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp; report-to=endpoint"]
    expected_out: Any = (Token("require-corp"), {"report-to": "endpoint"})
    expected_notes: NoteClassListType = [COEP_REQUIRE_CORP]

    def set_response_context(self, message: ResponseLinterProtocol) -> None:
        message.headers.process(
            [(b"Reporting-Endpoints", b'endpoint="https://example.com/reports"')]
        )


class CrossOriginEmbedderPolicyReportToMissingTest(FieldTest[ResponseLinterProtocol]):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp; report-to=endpoint"]
    expected_out: Any = (Token("require-corp"), {"report-to": "endpoint"})
    expected_notes: NoteClassListType = [COEP_REQUIRE_CORP, COEP_REPORT_TO_MISSING]
