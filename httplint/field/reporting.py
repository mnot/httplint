"""
Endpoint names for CSP, COEP, COOP and NEL.
"""

from typing import Set

from httplint.types import LinterProtocol


def report_to_groups(message: LinterProtocol) -> Set[str]:
    "Names of the groups defined by `Report-To` (the group member, which defaults to `default`)."
    groups: Set[str] = set()
    report_to_value = message.headers.parsed.get("report-to")
    if not isinstance(report_to_value, list):
        return groups
    for group in report_to_value:
        if not isinstance(group, dict):
            continue
        name = group.get("group", "default")
        if isinstance(name, str):
            groups.add(name)
    return groups


def known_reporting_endpoints(message: LinterProtocol, include_report_to: bool = False) -> Set[str]:
    """
    Names of the endpoints defined by `Reporting-Endpoints`; with `include_report_to`, the
    groups defined by `Report-To` as well.
    """
    endpoints_field = message.headers.parsed.get("reporting-endpoints")
    known: Set[str] = set(endpoints_field.keys()) if endpoints_field else set()
    if include_report_to:
        known |= report_to_groups(message)
    return known
