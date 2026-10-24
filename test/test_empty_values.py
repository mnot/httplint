"""
Crash sweep: every registered field must survive an empty, whitespace-only, or single-tab value,
in both requests and responses, through the real linter path.
"""

import inspect
import pkgutil
import sys
import traceback
import unittest
from typing import Any, List, Set, Tuple

import httplint.field.parsers as parsers
from httplint.field import HttpField, deprecated, unnecessary
from httplint.field.finder import HttpFieldFinder
from httplint.message import HttpRequestLinter, HttpResponseLinter

VALUES = [b"", b" ", b"\t"]

# Fields known to raise on one of VALUES (name, message type). Fix the field, then remove it.
KNOWN_FAILURES: Set[Tuple[str, str]] = set()


def field_names() -> List[str]:
    "Wire names for every registered field: parsers, aliases, deprecated, and unnecessary."
    names = set(HttpFieldFinder.field_aliases)
    names.update(deprecated.field_lookup.values())
    names.update(unnecessary.UNNECESSARY_FIELDS)
    for info in pkgutil.iter_modules(parsers.__path__):
        module = sys.modules[f"{parsers.__name__}.{info.name}"]
        found = False
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, HttpField) and cls.__module__ == module.__name__:
                canonical = getattr(cls, "canonical_name", None)
                if canonical:
                    names.add(canonical)
                    found = True
        if not found:
            names.add(info.name.replace("_", "-"))
    return sorted(names)


def lint(message_type: str, name: str, value: bytes) -> Any:
    "Run one field line through the linter the way the CLI does."
    if message_type == "request":
        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
        req.process_headers([(name.encode("ascii"), value)])
        req.feed_content(b"")
        req.finish_content(True)
        return req
    res = HttpResponseLinter()
    res.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    res.process_headers([(name.encode("ascii"), value)])
    res.feed_content(b"")
    res.finish_content(True)
    return res


class TestEmptyValues(unittest.TestCase):
    "No field may raise on an empty or whitespace-only value."

    def test_sweep_covers_known_fields(self) -> None:
        names = field_names()
        self.assertGreater(len(names), 100)
        self.assertIn("X-Frame-Options", names)
        self.assertIn("Cache-Control", names)

    def test_no_field_raises(self) -> None:
        failures = []
        for name in field_names():
            for message_type in ("request", "response"):
                if (name, message_type) in KNOWN_FAILURES:
                    continue
                for value in VALUES:
                    try:
                        lint(message_type, name, value)
                    except Exception:  # pylint: disable=broad-exception-caught
                        last = traceback.format_exc().strip().splitlines()[-3:]
                        failures.append(f"{name} ({message_type}) {value!r}: " + " | ".join(last))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
