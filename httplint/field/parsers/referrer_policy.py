from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType


class referrer_policy(HttpField):
    canonical_name = "Referrer-Policy"
    description = """\
The `Referrer-Policy` response header controls how much referrer information (sent via the `Referer`
header) should be included with requests."""
    reference = "https://www.w3.org/TR/referrer-policy/"
    syntax = rfc9110.token
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        valid_policies = []
        for token in self.value:
            if token in VALID_REFERRER_POLICIES:
                valid_policies.append(token)
            else:
                add_note(REFERRER_POLICY_UNKNOWN, policy=token)

        if not valid_policies:
            add_note(REFERRER_POLICY_EMPTY)
            return

        if len(valid_policies) > 1:
            add_note(REFERRER_POLICY_MULTIPLE, effective=valid_policies[-1])

        effective_policy = valid_policies[-1]
        if effective_policy == "unsafe-url":
            add_note(REFERRER_POLICY_UNSAFE)


class REFERRER_POLICY_UNSAFE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "This response's Referrer-Policy allows unsafe URLs."
    _text = """\
Using `unsafe-url` in `Referrer-Policy` means that the full URL (including query parameters) will
be sent as a referrer to all origins, including those that are not secure (HTTP). This can leak
sensitive information."""


class REFERRER_POLICY_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The Referrer-Policy value '%(policy)s' is unknown."
    _text = """\
The `Referrer-Policy` header contains the value `%(policy)s`, which is not a known referrer policy.
It will be ignored by browsers."""


class REFERRER_POLICY_EMPTY(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "No valid Referrer-Policy found."
    _text = """\
The `Referrer-Policy` header does not contain any valid policies. Browsers will use their default
policy (usually `strict-origin-when-cross-origin`)."""


class REFERRER_POLICY_MULTIPLE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "Multiple Referrer-Policy values found; only '%(effective)s' is used."
    _text = """\
The `Referrer-Policy` header contains multiple valid policies. Browsers will only use the last
valid policy found, which is `%(effective)s`. Earlier values are ignored."""


VALID_REFERRER_POLICIES = [
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "origin",
    "strict-origin",
    "origin-when-cross-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
]


class ReferrerPolicyTest(FieldTest):
    name = "Referrer-Policy"
    inputs = [b"no-referrer", b"unsafe-url"]
    expected_out = ["no-referrer", "unsafe-url"]
    expected_notes = [REFERRER_POLICY_UNSAFE, REFERRER_POLICY_MULTIPLE]


class ReferrerPolicyUnknownTest(FieldTest):
    name = "Referrer-Policy"
    inputs = [b"unknown-value"]
    expected_out = ["unknown-value"]
    expected_notes = [REFERRER_POLICY_UNKNOWN, REFERRER_POLICY_EMPTY]


class ReferrerPolicyOverrideTest(FieldTest):
    name = "Referrer-Policy"
    inputs = [b"unsafe-url, no-referrer"]
    expected_out = ["unsafe-url", "no-referrer"]
    expected_notes = [REFERRER_POLICY_MULTIPLE]
