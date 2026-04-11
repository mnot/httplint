from httplint.field import FIELD_DEPRECATED
from httplint.field.singleton_field import SingletonField
from httplint.field.tests import FieldTest
from httplint.note import categories
from httplint.types import (
    AnyMessageLinterProtocol,
    NoteClassListType,
)


class access_control(SingletonField[AnyMessageLinterProtocol]):
    canonical_name = "Access-Control"
    description = """\
The `Access-Control` header was an experimental header for controlling access to resources. It is
obsolete and should not be used."""
    reference = "https://www.w3.org/TR/2007/WD-access-control-20071126/#access-control0"
    syntax = False
    category = categories.SECURITY
    deprecated = True


class AccessControlTest(FieldTest[AnyMessageLinterProtocol]):
    name = "Access-Control"
    inputs = [b"foo"]
    expected_out = "foo"
    expected_notes: NoteClassListType = [FIELD_DEPRECATED]
