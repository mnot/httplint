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
from httplint.syntax.rfc7230 import list_rule


def checkRegistryCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/http-fields/http-fields.xml>,
    See what fields are missing and check those remaining to see what they don't define.
    """
    errors = 0
    unsupported = 0
    message = FakeMessageLinter()
    finder = HttpFieldFinder(message)
    for field_name in parseFieldRegistry(xml_file):
        field_cls = finder.find_handler_class(field_name)
        if field_cls is None:
            sys.stderr.write(f"* {field_name} unsupported\n")
            unsupported += 1
        else:
            errors += checkFieldClass(field_cls, field_name)
    return errors, unsupported


def parseFieldRegistry(xml_file):
    """
    Given a filename containing XML, parse it and return a list of registered field names.
    """

    tree = ET.parse(xml_file)
    root = tree.getroot()
    result = []
    for record in root.iter('{http://www.iana.org/assignments}record'):
        result.append(record.find('{http://www.iana.org/assignments}value').text)
    return result


NOT_PRESENT = "not present"

def checkFieldClass(field_cls, field_name):
    """
    Given a field class, make sure it's complete. Complain on STDERR if not.
    """

    errors = 0
    message = FakeMessageLinter()
    field = field_cls(field_name, None)
    attrs = dir(field)
    checks = [
        ('canonical_name', [str], True),
        ('reference', [str], True),
        ('description', [str], True),
        ('valid_in_requests', [bool, type(None)], True),
        ('valid_in_responses', [bool, type(None)], True),
        ('syntax', [str, list_rule], True),
        ('list_header', [bool], True),
        ('deprecated', [bool], False),
    ]
    for (attr_name, attr_types, attr_required) in checks:
        attr_value = getattr(field, attr_name, NOT_PRESENT)
        if getattr(field, "no_coverage", False) and attr_name in ['syntax', 'list_header']:
            continue
        if attr_name in ['syntax'] and attr_value is False:
            continue
        if attr_required and attr_value == NOT_PRESENT:
            sys.stderr.write(f"* {field_name} lacks {attr_name}\n")
        elif True not in [isinstance(attr_value, t) for t in attr_types]:
            sys.stderr.write(f"* {field_name} WRONG TYPE FOR {attr_name}\n")
            errors += 1

    canonical_name = getattr(field, "canonical_name", None)
    if canonical_name != field_name:
        sys.stderr.write(f"* {field_name} CANONICAL MISMATCH ({canonical_name})\n")
        errors += 1

    if field.no_coverage is False:
        loader = unittest.TestLoader()
        finder = HttpFieldFinder(message)
        field_mod = finder.find_module(field_name)
        tests = loader.loadTestsFromModule(field_mod)
        if tests.countTestCases() == 0:
            sys.stderr.write(f"* {field_name} NO TESTS\n")
    return errors

if __name__ == "__main__":
    print("## Checking Fields...")
    errors, unsupported = checkRegistryCoverage(sys.argv[1])
    print(f"{errors} errors; {unsupported} unsupported.")
    if errors > 0:
        sys.exit(1)
