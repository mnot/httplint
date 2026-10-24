from typing import Dict, Optional, Type

from http_sf import Token

from httplint.field.reporting import known_reporting_endpoints
from httplint.field.structured_field import StructuredField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, ResponseLinterProtocol, SFItemType


class TokenPolicyField(StructuredField[ResponseLinterProtocol]):
    """
    A Structured Field Item whose value is a Token naming a policy, with an optional `report-to`
    parameter naming a reporting endpoint (Cross-Origin-Embedder-Policy and
    Cross-Origin-Opener-Policy, and their Report-Only variants).

    Subclasses supply the data: the note for each known value, the notes for a bad value and a
    missing endpoint, and -- for a Report-Only variant -- the name of the enforcing field.
    """

    syntax = False  # Structured Field
    category = categories.SECURITY
    deprecated = False
    sf_type = "item"
    value: SFItemType

    policy_notes: Dict[str, Type[Note]] = {}
    bad_value_note: Type[Note]
    report_to_missing_note: Type[Note]
    enforcing_name = ""  # lower-case name of the enforcing field, for Report-Only variants
    report_only_duplicate_note: Optional[Type[Note]] = None
    report_only_string = ""
    report_only_text = ""

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if (
            self.enforcing_name
            and self.report_only_duplicate_note
            and self.enforcing_name in self.message.headers.handlers
        ):
            add_note(self.report_only_duplicate_note)

        val = self.value[0]
        policy_note = self.policy_notes.get(str(val)) if isinstance(val, Token) else None
        if policy_note is None:
            add_note(self.bad_value_note, value=val, report_only=self.report_only_string)
        else:
            add_note(
                policy_note,
                report_only=self.report_only_string,
                report_only_text=self.report_only_text,
            )

    def post_check(self, add_note: AddNoteMethodType) -> None:
        if self.value is None:
            return
        params = self.value[1]
        if "report-to" not in params:
            return
        report_to = params["report-to"]

        # HTML only uses the parameter if it is a String, not a Token or anything else.
        if not isinstance(report_to, str):
            add_note(POLICY_REPORT_TO_NOT_STRING, report_only=self.report_only_string)
            return
        if report_to not in known_reporting_endpoints(self.message):
            add_note(
                self.report_to_missing_note,
                endpoint=report_to,
                report_only=self.report_only_string,
            )


class POLICY_REPORT_TO_NOT_STRING(Note):
    category = categories.SECURITY
    level = levels.WARN
    _summary = "The report-to parameter in %(field_name)s isn't a String%(report_only)s."
    _text = """\
The `report-to` parameter in the `%(field_name)s` header names a reporting endpoint, and has to be
a String (for example, `report-to="endpoint"`). Browsers may ignore the parameter when it is a
Token (`report-to=endpoint`) or any other type."""
