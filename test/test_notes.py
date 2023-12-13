"""
Check all Note definitions.
"""

import re

from httplint.note import Note, categories, levels

from utils import checkSubClasses


def checkNote(note_cls):
    note_name = note_cls.__name__
    assert isinstance(note_cls.category, categories), note_name
    assert isinstance(note_cls.level, levels), note_name
    assert isinstance(note_cls._summary, str), note_name
    assert note_cls._summary != "", note_name
    assert not re.search(r"\s{2,}", note_cls._summary), note_name
    assert isinstance(note_cls._text, str), note_name
    return 0


if __name__ == "__main__":
    print("Checking Notes...")
    paths = ["httplint", "httplint/field", "httplint/field/parsers"]
    count, errors = checkSubClasses(Note, paths, checkNote)
    print(f"{count} checked; {errors} errors.")
