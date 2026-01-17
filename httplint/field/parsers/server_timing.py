from typing import Tuple

from httplint.field.list_field import HttpListField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params


class server_timing(HttpListField):
    canonical_name = "Server-Timing"
    description = """\
The `Server-Timing` header field communicates one or more metrics and descriptions for the given
request-response cycle. It is used to surface any backend server timing metrics (e.g. database
read/write, CPU time, file system access, etc.) in the developer tools in the browser or any other
consumer of Server-Timing."""
    reference = "https://w3c.github.io/server-timing/#the-server-timing-header-field"
    syntax = rfc9110.list_rule(rf"{rfc9110.token} {rfc9110.parameters}")
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    structured_field = False

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, ParamDictType]:
        try:
            metric_name, param_str = field_value.split(";", 1)
        except ValueError:
            metric_name, param_str = field_value, ""

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


class ServerTimingTest(FieldTest):
    name = "Server-Timing"
    inputs = [b"miss, db;dur=53, app;dur=47.2"]
    expected_out = [("miss", {}), ("db", {"dur": "53"}), ("app", {"dur": "47.2"})]
    expected_notes = [
        SERVER_TIMING_MISSING_DUR,
        SERVER_TIMING_MISSING_DESC,  # miss
        SERVER_TIMING_MISSING_DESC,  # db
        SERVER_TIMING_MISSING_DESC,  # app
    ]


class ServerTimingDescTest(FieldTest):
    name = "Server-Timing"
    inputs = [b'cache;desc="Cache Read", db;dur=50;desc="Database"']
    expected_out = [
        ("cache", {"desc": "Cache Read"}),
        ("db", {"dur": "50", "desc": "Database"}),
    ]
    expected_notes = [
        SERVER_TIMING_MISSING_DUR,  # cache
    ]


class ServerTimingBadDurTest(FieldTest):
    name = "Server-Timing"
    inputs = [b"db;dur=foo"]
    expected_out = [("db", {"dur": "foo"})]
    expected_notes = [SERVER_TIMING_BAD_PARAM, SERVER_TIMING_MISSING_DESC]
