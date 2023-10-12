"""
Check coverage and definitions of HTTP fields.
"""

import os
import sys
import types
import unittest
import xml.etree.ElementTree as ET

from httplint.fields import HttpField
from httplint.field_section import FieldSection
from httplint.syntax.rfc7230 import list_rule


def checkRegistryCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/http-fields/http-fields.xml>,
    See what fields are missing and check those remaining to see what they don't define.
    """
    errors = 0
    for field_name in parseFieldRegistry(xml_file):
        field_cls = FieldSection.find_handler(field_name, default=False)
        if not field_cls:
            sys.stderr.write(f"* {field_name} unsupported\n")
        else:
            errors += checkFieldClass(field_cls)
    return errors


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


def checkFieldClass(field_cls):
    """
    Given a field class, make sure it's complete. Complain on STDERR if not.
    """

    errors = 0
    field_name = getattr(field_cls, 'canonical_name', field_cls.__name__)
    attrs = dir(field_cls)
    checks = [
        ('canonical_name', [str], True),
        ('reference', [str], True),
        ('description', [str], True),
        ('valid_in_requests', [bool], True),
        ('valid_in_responses', [bool], True),
        ('syntax', [str, list_rule], True),
        ('list_header', [bool], True),
        ('deprecated', [bool], False),
    ]
    for (attr_name, attr_types, attr_required) in checks:
        attr_value = getattr(field_cls, attr_name, None)
        if getattr(field_cls, "no_coverage", False) and attr_name in ['syntax']:
            continue
        if attr_name in ['syntax'] and attr_value == False:
            continue
        if attr_required and attr_value is None:
            sys.stderr.write(f"* {field_name} lacks {attr_name}\n")
        elif True not in [isinstance(attr_value, t) for t in attr_types]:
            sys.stderr.write(f"* {field_name} WRONG TYPE FOR {attr_name}\n")
            errors += 1

    canonical_name = getattr(field_cls, "canonical_name", None)
    if canonical_name != field_name:
        sys.stderr.write(f"* {field_name} CANONICAL MISMATCH ({canonical_name})\n")
        errors += 1

    loader = unittest.TestLoader()
    field_mod = FieldSection.find_field_module(field_name)
    tests = loader.loadTestsFromModule(field_mod)
    if tests.countTestCases() == 0 and getattr(field_cls, "no_coverage", True) == False:
        sys.stderr.write(f"* {field_name} NO TESTS\n")
    return errors

if __name__ == "__main__":
    print("## Checking Fields...")
    errors = checkRegistryCoverage(sys.argv[1])
    print(f"{errors} errors.")
    if errors > 0:
        sys.exit(1)
