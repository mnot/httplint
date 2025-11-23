from http_sf import Token

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class permissions_policy(HttpField):
    canonical_name = "Permissions-Policy"
    description = """\
The `Permissions-Policy` response header allows a site to allow or deny the use of browser features,
such as the camera, microphone, or geolocation, in its own frame, and in iframes that it embeds."""
    reference = "https://www.w3.org/TR/permissions-policy/"

    syntax = False  # Uses SF parser
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = True
    sf_type = "dictionary"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return
        for feature, allowlist in self.value.items():
            val, _ = allowlist
            if isinstance(val, list):
                for item in val:
                    i_val, _ = item
                    if isinstance(i_val, Token):
                        if str(i_val) not in ["self", "src"]:
                            add_note(
                                PERMISSIONS_POLICY_UNKNOWN_TOKEN,
                                token=str(i_val),
                                feature=feature,
                            )
                    elif isinstance(i_val, str):
                        if i_val in ["self", "src", "*", "none"]:
                            add_note(
                                PERMISSIONS_POLICY_QUOTED_KEYWORD,
                                value=i_val,
                                feature=feature,
                            )
                    else:
                        add_note(
                            PERMISSIONS_POLICY_INVALID_ITEM_TYPE,
                            item=str(i_val),
                            feature=feature,
                        )
            elif isinstance(val, Token):
                if val != "*":
                    add_note(PERMISSIONS_POLICY_INVALID_VALUE, feature=feature)
            else:
                add_note(PERMISSIONS_POLICY_INVALID_VALUE, feature=feature)

            if feature not in SENSITIVE_FEATURES:
                continue
            if isinstance(val, Token) and val == "*":
                add_note(PERMISSIONS_POLICY_WILDCARD, feature=feature)


class PERMISSIONS_POLICY_WILDCARD(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The '%(feature)s' feature is allowed for all origins."
    _text = """\
The `Permissions-Policy` header allows the `%(feature)s` feature for all origins (using `*`).
This is insecure and should be restricted to specific origins or `self`."""


class PERMISSIONS_POLICY_INVALID_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The value for '%(feature)s' should be an Inner List or the token '*'."
    _text = """\
The value for the `%(feature)s` feature in `Permissions-Policy` is invalid. It should be either
an Inner List of origins (e.g., `(self "https://example.com")`) or the special token `*`."""


class PERMISSIONS_POLICY_UNKNOWN_TOKEN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The token '%(token)s' is not valid in a Permissions Policy allowlist."
    _text = """\
The token `%(token)s` is not a valid keyword in a `Permissions-Policy` allowlist.
Valid tokens are `self` and `src`."""


class PERMISSIONS_POLICY_QUOTED_KEYWORD(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The value '%(value)s' looks like a keyword but is a string."
    _text = """\
The value `%(value)s` is a string, but it looks like a keyword.
If you meant to use the keyword, remove the quotes (e.g., `self` instead of `"self"`)."""


class PERMISSIONS_POLICY_INVALID_ITEM_TYPE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = (
        "The item '%(item)s' is not a valid type for a Permissions Policy allowlist."
    )
    _text = """\
The item `%(item)s` is not a valid type for a `Permissions-Policy` allowlist.
Allowlists should contain origins (strings) or keywords (tokens)."""


SENSITIVE_FEATURES = [
    "camera",
    "microphone",
    "geolocation",
    "payment",
    "usb",
    "serial",
    "magnetometer",
    "accelerometer",
    "gyroscope",
    "screen-wake-lock",
]


class PermissionsPolicyTest(FieldTest):
    name = "Permissions-Policy"
    inputs = [b"geolocation=(), camera=self"]
    expected_out = {"geolocation": ([], {}), "camera": (Token("self"), {})}
    expected_notes = [PERMISSIONS_POLICY_INVALID_VALUE]


class PermissionsPolicyWildcardTest(FieldTest):
    name = "Permissions-Policy"
    inputs = [b"geolocation=*, camera=()"]
    expected_out = {"geolocation": (Token("*"), {}), "camera": ([], {})}
    expected_notes = [PERMISSIONS_POLICY_WILDCARD]


class PermissionsPolicyInvalidTest(FieldTest):
    name = "Permissions-Policy"
    inputs = [b'geolocation=("self"), camera=(none)']
    expected_out = {
        "geolocation": ([("self", {})], {}),
        "camera": ([(Token("none"), {})], {}),
    }
    expected_notes = [
        PERMISSIONS_POLICY_QUOTED_KEYWORD,
        PERMISSIONS_POLICY_UNKNOWN_TOKEN,
    ]
