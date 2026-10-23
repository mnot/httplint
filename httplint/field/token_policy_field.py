from typing import Dict, Optional, Type

from http_sf import Token

from httplint.field.structured_field import StructuredField
from httplint.field.utils import known_reporting_endpoints
from httplint.note import Note, categories
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
        report_to = self.value[1].get("report-to")
        if not report_to:
            return

        if report_to not in known_reporting_endpoints(self.message):
            add_note(
                self.report_to_missing_note,
                endpoint=report_to,
                report_only=self.report_only_string,
            )
