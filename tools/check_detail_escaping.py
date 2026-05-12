"""
Scan all Note subclasses and report _text templates where user-controlled
vars appear in plain paragraph text (not protected by a backtick code span
or a 4-space indented code block).

A var reference in a code span or indented block is safe because the
Markdown renderer escapes it exactly once.  A var in plain paragraph text
is passed through as raw HTML, which is an XSS risk.

Usage:
    PYTHONPATH=. python tools/check_detail_escaping.py
"""

import importlib
import inspect
import pkgutil
import re
import sys

import httplint


# ---------------------------------------------------------------------------
# Vars that are always controlled by the library, never by HTTP input.
#
# A var belongs here when ALL of the following are true:
#   1. Its value is computed or chosen by library code, not copied from the
#      wire (header name, header value, URI, etc.).
#   2. Its character set is provably HTML-safe — e.g. an integer, an
#      ISO-formatted date, a Python type name, or a string chosen from a
#      fixed set like {"request", "response"}.
#   3. OR it is pre-formatted by library code that already wraps the
#      user-facing portions in backtick spans (e.g. markdown_list / _make_list).
#
# If you add a new Note that uses one of these var names for *HTTP input*,
# remove the name from this set and wrap the var in a backtick span instead.
# ---------------------------------------------------------------------------

KNOWN_SAFE_VARS: frozenset[str] = frozenset(
    {
        # always supplied by the library, never from the wire
        "field_name",
        "subject",
        # library-computed cache ages / freshness lifetimes (human-readable strings)
        "current_age",
        "freshness_lifetime",
        "fresh_lifetime",
        "fresh_left",
        "share_lifetime",
        "share_left",
        # byte-count integers
        "content_length",
        "ok_brotli_len",
        "ok_zlib_len",
        "server_length",
        "set_cookie_value_length",
        # other numeric / constrained values
        "post_check",   # Cache-Control integer directive, validated before use
        "pre_check",    # Cache-Control integer directive, validated before use
        "duration",     # library-formatted duration (Max-Age / Expires)
        # library-formatted date strings (not raw wire values)
        "date",
        "last_modified_string",
        # library URIs (set as class attributes, not from the wire)
        "ref_uri",
        "deprecation_ref",
        # type-name strings chosen by the library ("string", "integer", …)
        "expected_type",
        "expected",
        "item_type",
        # fixed-vocabulary strings: "request" / "response"
        "message_type",
        "other_message",
        # HTTP request methods — constrained alphabet, no HTML special chars
        "method",
        # HTTP status codes — integers or short library-chosen phrases
        "status",
        # library-generated prose appended to report-only variants
        "report_only_text",
        # pre-formatted lists: markdown_list() / _make_list() already add backticks
        "conflicts",
        "directives_list",
        "headers",
        # SF-constrained: missing Vary fields come from Accept-CH Tokens
        "missing_fields",
        # SF dict keys: [a-z0-9_\-.*] only, no HTML special chars
        "key",
        # "context" in DUPLICATE_KEY is a word like "inner" from http_sf;
        # "context" in STRUCTURED_FIELD_PARSE_ERROR is either "" or a 4-space
        # indented block that Markdown puts in a <pre> and escapes.
        "context",
        # HTTP parameter names follow token syntax; no < > & allowed
        "param",
        # library error messages with static text (not echoing wire values)
        "problem",   # RANGE_BAD_SYNTAX: all values are library string literals
        "details",   # NEL: all values are library string literals
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_protected(text: str) -> str:
    """Remove content that is protected by Markdown escaping."""
    # Remove 4-space indented lines
    text = re.sub(r"(?m)^    .*$", "", text)
    # Remove fenced code blocks (``` or ~~~)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.DOTALL)
    # Remove inline code spans (backtick sequences)
    text = re.sub(r"`[^`]*`", "", text)
    return text


def _vars_in_plain_text(template: str) -> list[str]:
    """Return var names that appear outside protected regions."""
    unprotected = _strip_protected(template)
    return re.findall(r"%\((\w+)\)s", unprotected)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _iter_note_subclasses():
    """Yield (module, class_name, cls) for every Note subclass found."""
    from httplint.note import Note

    def _load_all(package):
        try:
            for _importer, modname, _ispkg in pkgutil.walk_packages(
                path=package.__path__,
                prefix=package.__name__ + ".",
                onerror=lambda _: None,
            ):
                try:
                    importlib.import_module(modname)
                except Exception:
                    pass
        except AttributeError:
            pass

    _load_all(httplint)

    seen = set()
    for cls in Note.__subclasses__():
        queue = [cls]
        while queue:
            c = queue.pop()
            if c in seen:
                continue
            seen.add(c)
            queue.extend(c.__subclasses__())
            yield inspect.getmodule(c), c.__name__, c


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    problems = []

    for module, cls_name, cls in _iter_note_subclasses():
        template = getattr(cls, "_text", "")
        if not template:
            continue

        plain_vars = _vars_in_plain_text(template)
        risky = [v for v in plain_vars if v not in KNOWN_SAFE_VARS]

        if risky:
            mod_name = module.__name__ if module else "<unknown>"
            problems.append((mod_name, cls_name, risky, template))

    if not problems:
        print("No unprotected vars found in _text templates.")
        return 0

    print(f"Found {len(problems)} Note class(es) with unprotected _text vars:\n")
    for mod_name, cls_name, risky, template in sorted(problems):
        print(f"  {mod_name}.{cls_name}")
        print(f"    Unprotected vars: {', '.join(risky)}")
        unprotected = _strip_protected(template)
        for line in unprotected.splitlines():
            if any(f"%({v})s" in line for v in risky):
                print(f"    > {line.strip()!r}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
