"""
Check all Note definitions.
"""

import re

from httplint.note import _DIRECTIVE_RE, Note, categories, levels

from utils import checkSubClasses


def checkNote(note_cls):
    note_name = note_cls.__name__
    assert isinstance(note_cls.category, categories), note_name
    assert isinstance(note_cls.level, levels), note_name
    assert isinstance(note_cls._summary, str), note_name
    assert note_cls._summary != "", note_name
    assert not re.search(r"\s{2,}", note_cls._summary), note_name
    assert isinstance(note_cls._text, str), note_name

    # Render summary and detail with a synthetic value for every named
    # %-directive in the templates -- 1 satisfies every conversion
    # character _DIRECTIVE_RE matches (%d, %s, %f, %c, etc.), so this
    # doesn't need to know each directive's expected type. Catches a
    # %-format/directive-name mismatch (the kind of bug #163 was filed
    # about) for every note at test time, not just the ones smoke.py
    # happens to trigger at runtime.
    var_names = {n for n, _ in _DIRECTIVE_RE.findall(note_cls._summary + note_cls._text)}
    note = note_cls("test-subject", **{n: 1 for n in var_names})
    note.summary  # pylint: disable=pointless-statement
    note.detail  # pylint: disable=pointless-statement
    return 0


if __name__ == "__main__":
    print("Checking Notes...")
    paths = ["httplint", "httplint/field", "httplint/field/parsers"]
    count, errors = checkSubClasses(Note, paths, checkNote)
    print(f"{count} checked; {errors} errors.")
