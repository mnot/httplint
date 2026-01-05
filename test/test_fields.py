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
from httplint.field.section import FieldSection
from httplint.field.tests import FakeResponseLinter
from httplint.syntax.rfc9110 import list_rule

from utils import checkSubClasses


def checkRegistryCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/http-fields/http-fields.xml>,
    See what fields are missing and check those remaining to see what they don't define.
    """
    unsupported = 0
    message = FakeResponseLinter()
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

    if not hasattr(field_cls, "canonical_name"):
        return 0

    errors = 0
    message = FakeResponseLinter()
    field = field_cls("warning", None)
    attrs = dir(field)
    checks = [
        ("canonical_name", [str], True),
        ("reference", [str], True),
        ("description", [str], True),
        ("valid_in_requests", [bool, type(None)], True),
        ("valid_in_responses", [bool, type(None)], True),
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


class TestFieldFinder(unittest.TestCase):
    def setUp(self) -> None:
        self.message = FakeResponseLinter()
        self.finder = HttpFieldFinder(self.message)

    def test_find_handler(self) -> None:
        handler = self.finder.find_handler("Content-Type")
        self.assertEqual(handler.canonical_name, "Content-Type")

    def test_find_handler_case_insensitive(self) -> None:
        handler = self.finder.find_handler("cOnTeNt-TyPe")
        self.assertEqual(handler.canonical_name, "Content-Type")

    def test_find_unknown_handler(self) -> None:
        handler = self.finder.find_handler("Unknown-Header")
        self.assertEqual(handler.canonical_name, "Unknown-Header")


class TestFieldSection(unittest.TestCase):
    def setUp(self) -> None:
        self.message = FakeResponseLinter()
        self.section = FieldSection(self.message)

    def test_process(self) -> None:
        headers = [(b"Content-Type", b"text/plain")]
        self.section.process(headers)
        self.assertIn("content-type", self.section.parsed)

    def test_process_multiple(self) -> None:
        headers = [(b"Content-Type", b"text/plain"), (b"Content-Length", b"10")]
        self.section.process(headers)
        self.assertIn("content-type", self.section.parsed)
        self.assertIn("content-length", self.section.parsed)





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
