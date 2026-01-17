from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax.rfc9110 import list_rule, quoted_string
from httplint.types import AddNoteMethodType
from httplint.field import BAD_SYNTAX
from httplint.message import HttpMessageLinter


class clear_site_data(HttpListField):
    canonical_name = "Clear-Site-Data"
    description = """\
The `Clear-Site-Data` header clears the data associated with the requesting website in the user's
browser. It allows web developers to have more control over the data stored by a client for their
origin."""
    reference = "https://www.w3.org/TR/clear-site-data/#field-clear-site-data"
    syntax = list_rule(quoted_string, 1)
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    KNOWN_VALUES = {"cache", "cookies", "storage", "executionContexts", "*"}

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        super().__init__(wire_name, message)
        self._unquoted_values: list[str] = []

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        if len(field_value) >= 2 and field_value[0] == '"' and field_value[-1] == '"':
            value = field_value[1:-1]
        else:
            value = field_value
            if value in self.KNOWN_VALUES:
                self._unquoted_values.append(value)

        # Check for empty value
        if value == "":
            add_note(CSD_EMPTY)
            return value

        # Check for valid values
        if value not in self.KNOWN_VALUES:
            add_note(CSD_UNKNOWN_VALUE, value=value)

        return value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if self._unquoted_values:
            add_note(CSD_UNQUOTED, values=", ".join(self._unquoted_values))
        if not self.value:
            add_note(CSD_EMPTY)


class CSD_UNKNOWN_VALUE(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The Clear-Site-Data header contains an unknown value '%(value)s'."
    _text = """\
The `Clear-Site-Data` header contains a value that is not recognized.
Valid values are: `"cache"`, `"cookies"`, `"storage"`, `"executionContexts"`, `"*"`."""


class CSD_EMPTY(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The Clear-Site-Data header has an empty value."
    _text = """\
The `Clear-Site-Data` header value is empty. It should contain at least one directive."""


class CSD_UNQUOTED(Note):
    category = categories.SECURITY
    level = levels.INFO
    _summary = "Clear-Site-Data contains unquoted values."
    _text = """\
Values in the `Clear-Site-Data` header must be quoted; unquoted values will be ignored. 

The following values were found unquoted: %(values)s."""


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
    expected_notes = [CSD_UNKNOWN_VALUE]


class ClearSiteDataEmptyTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b'""']
    expected_out = [""]
    expected_notes = [CSD_EMPTY]


class ClearSiteDataTrulyEmptyTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b""]
    expected_out = []
    expected_notes = [CSD_EMPTY]


class ClearSiteDataBadSyntaxTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b"foo"]
    expected_out = ["foo"]
    expected_notes = [BAD_SYNTAX, CSD_UNKNOWN_VALUE]


class ClearSiteDataUnquotedTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b"cache"]
    expected_out = ["cache"]
    expected_notes = [BAD_SYNTAX, CSD_UNQUOTED]


class ClearSiteDataMultipleUnquotedTest(FieldTest):
    name = "Clear-Site-Data"
    inputs = [b"cache, cookies"]
    expected_out = ["cache", "cookies"]
    expected_notes = [BAD_SYNTAX, CSD_UNQUOTED]
