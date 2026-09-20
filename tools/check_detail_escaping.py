"""
Scan all Note subclasses and report _text templates where user-controlled
vars appear in plain paragraph text (not protected by a backtick code span
or a 4-space indented code block).

Note._get_detail() renders every var not in KNOWN_SAFE_VARS as an opaque,
HTML-escaped placeholder, whether or not it's wrapped in a code span, so
this is no longer a security gate — an unprotected var is inert, just
unstyled. It remains a readability check: a wire value rendered as running
prose, indistinguishable from the template's own words, is worth flagging
even when it's safe.

Usage:
    PYTHONPATH=. python tools/check_detail_escaping.py
"""

import importlib
import inspect
import pkgutil
import re
import sys

import httplint
from httplint.note import KNOWN_SAFE_VARS


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
        unwrapped = [v for v in plain_vars if v not in KNOWN_SAFE_VARS]

        if unwrapped:
            mod_name = module.__name__ if module else "<unknown>"
            problems.append((mod_name, cls_name, unwrapped, template))

    if not problems:
        print("No unwrapped vars found in _text templates.")
        return 0

    print(f"Found {len(problems)} Note class(es) with unwrapped _text vars:\n")
    for mod_name, cls_name, unwrapped, template in sorted(problems):
        print(f"  {mod_name}.{cls_name}")
        print(f"    Unwrapped vars: {', '.join(unwrapped)}")
        unprotected = _strip_protected(template)
        for line in unprotected.splitlines():
            if any(f"%({v})s" in line for v in unwrapped):
                print(f"    > {line.strip()!r}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
