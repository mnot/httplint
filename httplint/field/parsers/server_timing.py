from typing import Tuple

from httplint.field import BAD_SYNTAX, BAD_SYNTAX_DETAILED
from httplint.field.list_field import HttpListField
from httplint.field.params import PARAM_REPEATS, parse_params, split_params_off
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc9110
from httplint.types import (
    AddNoteMethodType,
    NoteClassListType,
    ParamDictType,
    ResponseLinterProtocol,
)


class server_timing(HttpListField[ResponseLinterProtocol]):
    canonical_name = "Server-Timing"
    description = """\
The `Server-Timing` header field communicates one or more metrics and descriptions for the given
request-response cycle. It is used to surface any backend server timing metrics (e.g. database
read/write, CPU time, file system access, etc.) in the developer tools in the browser or any other
consumer of Server-Timing."""
    reference = "https://w3c.github.io/server-timing/#the-server-timing-header-field"
    syntax = rfc9110.list_rule(rf"{rfc9110.token} {rfc9110.parameters}")
    deprecated = False
    structured_field = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        metric_name, param_str = split_params_off(field_value)
        metric_name = metric_name.strip()
        param_dict = parse_params(param_str, add_note, ["desc"])

        return metric_name, param_dict

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        for metric_name, params in self.value:
            # Validate 'dur'
            duration = params.get("dur")
            if duration is None:
                add_note(SERVER_TIMING_MISSING_DUR, metric=metric_name)
            else:
                try:
                    float(duration)
                except ValueError:
                    add_note(
                        SERVER_TIMING_BAD_PARAM,
                        metric=metric_name,
                        param="dur",
                        value=duration,
                    )

            # Validate 'desc'
            if "desc" not in params:
                add_note(SERVER_TIMING_MISSING_DESC, metric=metric_name)


class SERVER_TIMING_BAD_PARAM(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter on the '%(metric)s' metric has a non-numeric value."
    _text = """\
The `%(param)s` parameter on the `%(metric)s` metric of the Server-Timing header requires a
valid number, but `%(value)s` was found.
"""


class SERVER_TIMING_MISSING_DUR(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The '%(metric)s' metric is missing the 'dur' parameter."
    _text = """\
The `%(metric)s` metric in the Server-Timing header is missing the `dur` (duration) parameter.

This parameter isn't required, but without it browsers may not be able to usefully display it.
"""


class SERVER_TIMING_MISSING_DESC(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The '%(metric)s' metric is missing the 'desc' parameter."
    _text = """\
The `%(metric)s` metric in the Server-Timing header is missing the `desc` (description) parameter.

Descriptions can help contextualise a metric when displayed.
"""


class ServerTimingTest(FieldTest[ResponseLinterProtocol]):
    name = "Server-Timing"
    inputs = [b"miss, db;dur=53, app;dur=47.2"]
    expected_out = [("miss", {}), ("db", {"dur": "53"}), ("app", {"dur": "47.2"})]
    expected_notes: NoteClassListType = [
        SERVER_TIMING_MISSING_DUR,
        SERVER_TIMING_MISSING_DESC,  # miss
        SERVER_TIMING_MISSING_DESC,  # db
        SERVER_TIMING_MISSING_DESC,  # app
    ]


class ServerTimingDescTest(FieldTest[ResponseLinterProtocol]):
    name = "Server-Timing"
    inputs = [b'cache;desc="Cache Read", db;dur=50;desc="Database"']
    expected_out = [
        ("cache", {"desc": "Cache Read"}),
        ("db", {"dur": "50", "desc": "Database"}),
    ]
    expected_notes: NoteClassListType = [
        SERVER_TIMING_MISSING_DUR,  # cache
    ]


class ServerTimingBadDurTest(FieldTest[ResponseLinterProtocol]):
    name = "Server-Timing"
    inputs = [b"db;dur=foo"]
    expected_out = [("db", {"dur": "foo"})]
    expected_notes: NoteClassListType = [SERVER_TIMING_BAD_PARAM, SERVER_TIMING_MISSING_DESC]


class ServerTimingRepeatedParamTest(FieldTest[ResponseLinterProtocol]):
    "Only the first instance of a parameter counts, even if it's invalid."

    name = "Server-Timing"
    inputs = [b'db;dur=53;dur=foo;desc="Database";desc="Other"']
    expected_out = [("db", {"dur": "53", "desc": "Database"})]
    expected_notes: NoteClassListType = [PARAM_REPEATS]


class ServerTimingInvalidFirstParamTest(FieldTest[ResponseLinterProtocol]):
    "An empty first dur is the first dur; the 5 after it is ignored."

    name = "Server-Timing"
    inputs = [b'db;dur=;dur=5;desc="x"']
    expected_out = [("db", {"desc": "x"})]
    expected_notes: NoteClassListType = [
        BAD_SYNTAX_DETAILED,
        PARAM_REPEATS,
        SERVER_TIMING_MISSING_DUR,
    ]


class ServerTimingQuotedSemicolonTest(FieldTest[ResponseLinterProtocol]):
    "Guard: the head is split off at the first ';' even inside quotes; it's invalid either way."

    name = "Server-Timing"
    inputs = [b'"a;b"']
    expected_out = [('"a', {})]
    expected_notes: NoteClassListType = [
        BAD_SYNTAX,
        SERVER_TIMING_MISSING_DUR,
        SERVER_TIMING_MISSING_DESC,
    ]


class ServerTimingNoWhitespaceBeforeSemicolonTest(FieldTest[ResponseLinterProtocol]):
    "Guard: no whitespace before ';'."

    name = "Server-Timing"
    inputs = [b"db;dur=53"]
    expected_out = [("db", {"dur": "53"})]
    expected_notes: NoteClassListType = [SERVER_TIMING_MISSING_DESC]


class ServerTimingSpaceBeforeSemicolonTest(FieldTest[ResponseLinterProtocol]):
    """
    Guard: this passes even if split_params_off() does not strip; server_timing.parse strips the
    metric name itself.
    """

    name = "Server-Timing"
    inputs = [b"db ;dur=53"]
    expected_out = [("db", {"dur": "53"})]
    expected_notes: NoteClassListType = [SERVER_TIMING_MISSING_DESC]


class ServerTimingTabBeforeSemicolonTest(FieldTest[ResponseLinterProtocol]):
    "Guard: see ServerTimingSpaceBeforeSemicolonTest."

    name = "Server-Timing"
    inputs = [b"db\t;dur=53"]
    expected_out = [("db", {"dur": "53"})]
    expected_notes: NoteClassListType = [SERVER_TIMING_MISSING_DESC]
