"""
Check all Note definitions.
"""

import importlib
import os
import pkgutil
import re
import sys

from httplint.note import Note, categories, levels


def checkNote(note_cls):
    note_name = note_cls.__name__
    assert isinstance(note_cls.category, categories), note_name
    assert isinstance(note_cls.level, levels), note_name
    assert isinstance(note_cls._summary, str), note_name
    assert note_cls._summary != "", note_name
    assert not re.search(r"\s{2,}", note_cls._summary), note_name
    assert isinstance(note_cls._text, str), note_name


def loadModules(paths, prefix):
    [ importlib.import_module(name) for finder, name, ispkg in pkgutil.iter_modules(paths, prefix=prefix) ]


def checkSubClasses(cls, check):
    """
    Run a check(subclass) function on all subclasses of cls.
    """
    loadModules(['httplint'], 'httplint.')
    loadModules(['httplint/field'], 'httplint.field.')
    loadModules(['httplint/field/parsers'], 'httplint.field.parsers.')
    count = 0
    for subcls in cls.__subclasses__():
        check(subcls)
        count += 1
    return count


if __name__ == "__main__":
    print("Checking Notes...")
    count = checkSubClasses(Note, checkNote)
    print(f"{count} checked.")
