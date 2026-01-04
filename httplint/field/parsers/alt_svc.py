from typing import Tuple, Union

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.field.notes import BAD_SYNTAX
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import AddNoteMethodType, ParamDictType


class alt_svc(HttpField):
    canonical_name = "Alt-Svc"
    description = """\
The `Alt-Svc` HTTP header field identifies an alternative service that can be arranged to access the
resources identifying the origin serving the field."""
    reference = "https://www.rfc-editor.org/rfc/rfc7838#section-3"
    syntax = (
        r"(?: clear | (?: "
        f"{rfc9110.token} = {rfc9110.quoted_string}"
        f"(?: {rfc9110.OWS} ; {rfc9110.OWS} {rfc9110.parameter} )* ) )"
    )
    list_header = True
    valid_in_requests = False
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Union[str, Tuple[str, str, ParamDictType]]:
        if field_value == "clear":
            return "clear"

        # Basic validation: must have an equals sign if not "clear".
        # If it doesn't, it doesn't match the general structure.
        if "=" not in field_value:
            raise ValueError

        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if isinstance(self.value, list):
            has_clear = "clear" in self.value
            if has_clear and len(self.value) > 1:
                add_note(ALTSVC_CLEAR_LIST)


class ALTSVC_CLEAR_LIST(Note):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "The Alt-Svc 'clear' token cannot be used with other values."
    _text = """\
The `Alt-Svc` header field value "clear" is used to invalidate previous alternative services.
It cannot be combined with other alternative service advertisements."""


class AltSvcTest(FieldTest):
    name = "Alt-Svc"
    inputs = [b'h2=":443"']
    expected_out = ['h2=":443"']


class AltSvcParamTest(FieldTest):
    name = "Alt-Svc"
    inputs = [b'h2=":443"; ma=60']
    expected_out = ['h2=":443"; ma=60']


class AltSvcClearTest(FieldTest):
    name = "Alt-Svc"
    inputs = [b"clear"]
    expected_out = ["clear"]


class AltSvcMixedTest(FieldTest):
    name = "Alt-Svc"
    inputs = [b'clear, h2=":443"']
    expected_out = ["clear", 'h2=":443"']
    expected_notes = [ALTSVC_CLEAR_LIST]


class AltSvcBadTest(FieldTest):
    name = "Alt-Svc"
    inputs = [b"foo"]
    expected_notes = [BAD_SYNTAX]
