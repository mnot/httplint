from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax.rfc9110 import list_rule, quoted_string
from httplint.types import AddNoteMethodType


class clear_site_data(HttpField):
    canonical_name = "Clear-Site-Data"
    description = """\
The `Clear-Site-Data` header clears the data associated with the requesting website in the user's
browser. It allows web developers to have more control over the data stored by a client for their
origin."""
    reference = "https://www.w3.org/TR/clear-site-data/#field-clear-site-data"
    syntax = list_rule(quoted_string, 1)
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        # Remove quotes
        value = field_value[1:-1]

        # Check for valid values
        if value not in ["cache", "cookies", "storage", "executionContexts", "*"]:
            add_note(UNKNOWN_VALUE, value=value)

        return value


class UNKNOWN_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The Clear-Site-Data header contains an unknown value '%(value)s'."
    _text = """\
The `Clear-Site-Data` header contains a value that is not recognized.
Valid values are: `"cache"`, `"cookies"`, `"storage"`, `"executionContexts"`, `"*"`."""


class ClearSiteDataTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b'"cache", "cookies"']
    expected_out = ["cache", "cookies"]


class ClearSiteDataWildcardTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b'"*"']
    expected_out = ["*"]


class ClearSiteDataUnknownTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b'"foo"']
    expected_out = ["foo"]
    expected_notes = [UNKNOWN_VALUE]
