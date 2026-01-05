from datetime import datetime
from typing import Any

from httplint.field.structured_field import StructuredField
from httplint.field.tests import FieldTest
from httplint.message import HttpMessageLinter
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class deprecation(StructuredField):
    canonical_name = "Deprecation"
    description = """\
The `Deprecation` header field allows a server to communicate to a client that the resource is or
will be deprecated."""
    reference = "https://www.rfc-editor.org/rfc/rfc9651.html"
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "item"

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if not self.value:
            return

        # self.value is (item, params) for Item
        item = self.value[0]

        if isinstance(item, datetime):
            if self.message.start_time:
                dep_time = item.timestamp()
                if dep_time > self.message.start_time:
                    add_note(DEPRECATION_FUTURE, date=item.isoformat())
                else:
                    add_note(DEPRECATION_PAST, date=item.isoformat())
        elif isinstance(item, bool):
            if item is True:
                add_note(DEPRECATION_TRUE)
            else:
                add_note(BAD_DEPRECATION_SYNTAX, item_type="Boolean False")
        else:
            add_note(BAD_DEPRECATION_SYNTAX, item_type=type(item).__name__)


class DEPRECATION_PAST(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The resource has been deprecated."
    _text = """\
The `Deprecation` header indicates that this resource was deprecated on %(date)s."""


class DEPRECATION_FUTURE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The resource will be deprecated."
    _text = """\
The `Deprecation` header indicates that this resource will be deprecated on %(date)s."""


class DEPRECATION_TRUE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The resource is deprecated."
    _text = """\
The `Deprecation` header indicates that this resource is deprecated."""


class BAD_DEPRECATION_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The Deprecation header has an invalid type."
    _text = """\
The `Deprecation` header value must be a Date or a Boolean True. Found: %(item_type)s."""


class DeprecationDateTest(FieldTest):
    name = "Deprecation"
    inputs = [b"@1672531199"]
    expected_out: Any = (datetime.fromtimestamp(1672531199), {})
    expected_notes = [DEPRECATION_PAST]

    def set_context(self, message: "HttpMessageLinter") -> None:
        message.start_time = 2000000000


class DeprecationBoolTest(FieldTest):
    name = "Deprecation"
    inputs = [b"?1"]
    expected_out: Any = (True, {})
    expected_notes = [DEPRECATION_TRUE]


class DeprecationFalseTest(FieldTest):
    name = "Deprecation"
    inputs = [b"?0"]
    expected_out: Any = (False, {})
    expected_notes = [BAD_DEPRECATION_SYNTAX]


class DeprecationInvalidTest(FieldTest):
    name = "Deprecation"
    inputs = [b"123"]
    expected_out: Any = (123, {})
    expected_notes = [BAD_DEPRECATION_SYNTAX]
