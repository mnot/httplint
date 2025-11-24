from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.field.utils import check_sf_item_token
from httplint.types import AddNoteMethodType


class cross_origin_embedder_policy(HttpField):
    canonical_name = "Cross-Origin-Embedder-Policy"
    description = """\
The `Cross-Origin-Embedder-Policy` header field prevents a document from loading any cross-origin
resources that don't explicitly grant the document permission (using CORP or CORS)."""
    reference = "https://html.spec.whatwg.org/multipage/origin.html#coep"
    syntax = False  # Structured Field
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "item"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        check_sf_item_token(
            self.value,
            [Token("require-corp"), Token("credentialless"), Token("unsafe-none")],
            add_note,
            CROSS_ORIGIN_EMBEDDER_POLICY,
            CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE,
        )


class CROSS_ORIGIN_EMBEDDER_POLICY(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "Cross-Origin-Embedder-Policy is set to '%(value)s'."
    _text = """\
The `Cross-Origin-Embedder-Policy` header controls whether the document can load cross-origin
resources.
"""


class CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Cross-Origin-Embedder-Policy has an invalid value '%(value)s'."
    _text = """\
The `Cross-Origin-Embedder-Policy` header must be one of `require-corp`, `credentialless`, or
`unsafe-none`.
"""


class CrossOriginEmbedderPolicyRequireCorpTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"require-corp"]
    expected_out = (Token("require-corp"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY]


class CrossOriginEmbedderPolicyCredentiallessTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"credentialless"]
    expected_out = (Token("credentialless"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY]


class CrossOriginEmbedderPolicyUnsafeNoneTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"unsafe-none"]
    expected_out = (Token("unsafe-none"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY]


class CrossOriginEmbedderPolicyBadValueTest(FieldTest):
    name = "Cross-Origin-Embedder-Policy"
    inputs = [b"foo"]
    expected_out = (Token("foo"), {})
    expected_notes = [CROSS_ORIGIN_EMBEDDER_POLICY_BAD_VALUE]
