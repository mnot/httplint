from typing import Any
from urllib.parse import urljoin, urlsplit

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class speculation_rules(StructuredField):
    canonical_name = "Speculation-Rules"
    description = """\
The `Speculation-Rules` header field allows the server to provide the client with a list of URLs that
point to speculation rules files."""
    reference = "https://wicg.github.io/nav-speculation/speculation-rules.html"
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "list"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        for item in self.value:
            url = item[0]
            if not isinstance(url, str):
                add_note(
                    BAD_SPECULATION_RULES_SYNTAX,
                    value=url,
                    found_type=type(url).__name__,
                )
                continue

            target = urljoin(self.message.base_uri, url)
            parsed = urlsplit(target)
            if parsed.scheme and parsed.scheme.lower() not in ["https", "wss"]:
                add_note(SPECULATION_RULE_NOT_SECURE, url=url)


class SPECULATION_RULE_NOT_SECURE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The speculation rule URL is not secure."
    _text = """\
The speculation rule `%(url)s` uses an insecure URL. Browsers may ignore it."""


class BAD_SPECULATION_RULES_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The speculation rule value is invalid."
    _text = """\
The speculation rule must be a string URL. Found: %(value)s (type `%(found_type)s`)."""


class SpeculationRulesTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b'"https://example.com/rules.json"']
    expected_out: Any = [("https://example.com/rules.json", {})]


class SpeculationRulesMultipleTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b'"https://example.com/rules1.json", "https://example.com/rules2.json"']
    expected_out: Any = [
        ("https://example.com/rules1.json", {}),
        ("https://example.com/rules2.json", {}),
    ]


class SpeculationRulesInsecureTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b'"http://example.com/rules.json"']
    expected_out: Any = [("http://example.com/rules.json", {})]
    expected_notes = [SPECULATION_RULE_NOT_SECURE]


class SpeculationRulesBadSyntaxTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b"123"]
    expected_out: Any = [(123, {})]
    expected_notes = [BAD_SPECULATION_RULES_SYNTAX]


class SpeculationRulesRelativeTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b'"/rules.json"']
    expected_out: Any = [("/rules.json", {})]
    expected_notes = []

    def set_context(self, message: Any) -> None:
        message.base_uri = "https://example.com/"


class SpeculationRulesRelativeInsecureTest(FieldTest):
    name = "Speculation-Rules"
    inputs = [b'"/rules.json"']
    expected_out: Any = [("/rules.json", {})]
    expected_notes = [SPECULATION_RULE_NOT_SECURE]

    def set_context(self, message: Any) -> None:
        message.base_uri = "http://example.com/"
