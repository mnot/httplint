"""
Check coverage and definitions of HTTP fields.
"""

import os
import sys
import types
import unittest
import xml.etree.ElementTree as ET

from httplint.field import HttpField
from httplint.field.finder import HttpFieldFinder
from httplint.field.tests import FakeMessageLinter
from httplint.syntax.rfc9110 import list_rule

from utils import checkSubClasses


def checkRegistryCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/http-fields/http-fields.xml>,
    See what fields are missing and check those remaining to see what they don't define.
    """
    unsupported = 0
    message = FakeMessageLinter()
    finder = HttpFieldFinder(message)
    for field_name, field_status in parseFieldRegistry(xml_file):
        field_cls = finder.find_handler_class(field_name)
        if field_cls is None:
            print(f"* {field_name} ({field_status})")
            unsupported += 1
    print()
    return unsupported


def parseFieldRegistry(xml_file):
    """
    Given a filename containing XML, parse it and return a list of registered field names.
    """

    tree = ET.parse(xml_file)
    root = tree.getroot()
    result = []
    for record in root.iter("{http://www.iana.org/assignments}record"):
        result.append(
            (
                record.find("{http://www.iana.org/assignments}value").text,
                record.find("{http://www.iana.org/assignments}status").text,
            )
        )
    return result


NOT_PRESENT = "not present"


def checkFieldClass(field_cls):
    """
    Given a field class, make sure it's complete. Complain on STDERR if not.
    """

    errors = 0
    message = FakeMessageLinter()
    field = field_cls("warning", None)
    attrs = dir(field)
    checks = [
        ("canonical_name", [str], True),
        ("reference", [str], True),
        ("description", [str], True),
        ("valid_in_requests", [bool, type(None)], True),
        ("valid_in_responses", [bool, type(None)], True),
        ("syntax", [str, list_rule], True),
        ("list_header", [bool], True),
        ("deprecated", [bool], False),
    ]
    for attr_name, attr_types, attr_required in checks:
        attr_value = getattr(field, attr_name, NOT_PRESENT)
        if attr_name in ["syntax"] and attr_value is False:
            continue
        if attr_required and attr_value == NOT_PRESENT:
            print(f"* {field_cls} lacks {attr_name}")
            errors += 1
        elif True not in [isinstance(attr_value, t) for t in attr_types]:
            print(f"* {field_cls} WRONG TYPE FOR {attr_name}")
            errors += 1

    canonical_name = getattr(field, "canonical_name", None)

    if canonical_name and getattr(field, "no_coverage", False) is False:
        loader = unittest.TestLoader()
        finder = HttpFieldFinder(message)
        field_mod = finder.find_module(canonical_name)
        tests = loader.loadTestsFromModule(field_mod)
        if tests.countTestCases() == 0:
            print(f"* {field_cls.__name__} NO TESTS")
    return errors


if __name__ == "__main__":
    print("# Checking Fields...")
    print("## Listing Unsupported Fields")
    unsupported = checkRegistryCoverage(sys.argv[1])
    print("## Checking Field Definitions")
    count, errors = checkSubClasses(
        HttpField, ["httplint/field/parsers"], checkFieldClass
    )
    print(f"{count} fields checked; {errors} errors; {unsupported} unsupported.")
    if errors > 0:
        sys.exit(1)
