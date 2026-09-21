"""
Scan all Note subclasses and report _text templates where a var appears
inline, mixed into a sentence of plain prose, without being protected by a
backtick code span or a 4-space indented code block.

This is a readability check, not a security gate. Note._get_detail() (in
httplint/note.py) treats every var as opaque, HTML-escaped wire data unless
its value is wrapped in MarkdownSafe -- so an unwrapped var can't produce
unescaped HTML, whether or not it's flagged here. What it CAN do is read as
running prose, indistinguishable from the template's own words; wrapping it
in backticks is worth doing for clarity even though it's optional for
safety.

There's no allowlist of "safe" var names to maintain. A var whose whole
line is just that one placeholder (plus, say, a trailing period) is a
block reference: it's standing in for a var whose value is a MarkdownSafe
block built by library code -- a bulleted list, an indented excerpt -- and
is *meant* to sit unwrapped, since the value supplies its own markup. That
shape is visible directly in the template text, so it doesn't need a name
on a list to recognize; only a var interpolated inline, alongside other
prose on its line, gets flagged.

Not run as part of `make test`: with no allowlist, it flags every
inline var that predates this check, including ones nobody's going to
rewrap just to silence a style nit. Run it by hand when touching a
template, or to survey the backlog.

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


def _is_block_reference(line: str) -> bool:
    """True if a template line is nothing but a single var reference (plus,
    maybe, trailing punctuation) -- the structural signature of a var whose
    value is meant to be its own Markdown block, not prose."""
    return bool(re.fullmatch(r"\s*%\(\w+\)s[.,:;]?\s*", line))


def _vars_in_plain_text(template: str) -> list[str]:
    """Return var names that appear outside protected regions, interpolated
    inline within a line of other prose rather than standing alone as a
    block reference. Each name is reported once, even if it's repeated on
    the same line or across several unwrapped lines."""
    unprotected = _strip_protected(template)
    risky: list[str] = []
    for line in unprotected.splitlines():
        if _is_block_reference(line):
            continue
        for name in re.findall(r"%\((\w+)\)s", line):
            if name not in risky:
                risky.append(name)
    return risky


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

        unwrapped = _vars_in_plain_text(template)

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
