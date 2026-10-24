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

from httplint.field import HttpField, deprecated, parsers, unnecessary
from httplint.field.finder import HttpFieldFinder
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import Note

VALUES = [b"", b" ", b"\t"]

# Fields known to raise on one of VALUES, as (name, message type). Each must still fail: the
# sweep reports an entry that no longer does, so fixed fields get removed from here.
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


def render(note: Note) -> None:
    "Render a note and its subnotes the way the CLI does, so rendering errors surface too."
    _ = (note.summary, note.detail)
    for subnote in note.subnotes:
        render(subnote)


def lint(message_type: str, name: str, value: bytes) -> Any:
    "Run one field line through the linter and render every note it produced."
    if message_type == "request":
        req = HttpRequestLinter()
        req.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
        req.process_headers([(name.encode("ascii"), value)])
        req.feed_content(b"")
        req.finish_content(True)
        for note in req.notes:
            render(note)
        return req
    res = HttpResponseLinter()
    res.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    res.process_headers([(name.encode("ascii"), value)])
    res.feed_content(b"")
    res.finish_content(True)
    for note in res.notes:
        render(note)
    return res


def sweep() -> Set[Tuple[str, str]]:
    "Return the (name, message type) pairs that raise on any of VALUES."
    failing = set()
    for name in field_names():
        for message_type in ("request", "response"):
            for value in VALUES:
                try:
                    lint(message_type, name, value)
                except Exception:  # pylint: disable=broad-exception-caught
                    failing.add((name, message_type))
                    print(f"{name} ({message_type}) {value!r}:", file=sys.stderr)
                    traceback.print_exc()
    return failing


class TestEmptyValues(unittest.TestCase):
    "No field may raise on an empty or whitespace-only value."

    def test_reaches_all_modules(self) -> None:
        reached = {
            module.__name__
            for module in (HttpFieldFinder.find_module(name) for name in field_names())
            if module
        }
        modules = {
            f"{parsers.__name__}.{info.name}" for info in pkgutil.iter_modules(parsers.__path__)
        }
        self.assertEqual(sorted(modules - reached), [])

    def test_no_field_raises(self) -> None:
        failing = sweep()
        self.assertEqual(sorted(failing - KNOWN_FAILURES), [], "new failures")
        self.assertEqual(sorted(KNOWN_FAILURES - failing), [], "stale KNOWN_FAILURES entries")


if __name__ == "__main__":
    unittest.main()
