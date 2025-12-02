#!/usr/bin/env python3
import sys
import os
import re

# Ensure we can import from the current directory (test/) and the project root
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "test"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from httplint.note import Note
from httplint.field import HttpField, deprecated, unnecessary
from httplint.field.finder import HttpFieldFinder
from utils import checkSubClasses

def dummy_check(note_cls):
    return 0

def get_note_count():
    paths = ["httplint", "httplint/field", "httplint/field/parsers"]
    count, _ = checkSubClasses(Note, paths, dummy_check)
    return count

def get_field_count():
    paths = ["httplint/field/parsers"]
    count, _ = checkSubClasses(HttpField, paths, dummy_check)
    count += len(deprecated.fields)
    count += len(unnecessary.UNNECESSARY_FIELDS)
    count += len(HttpFieldFinder.field_aliases)
    return count

def update_readme(note_count, field_count):
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()
    
    # Pattern to match: "httplint can report on nnn different aspects..."
    pattern = r"httplint can report on (\d+|nnn) different aspects of your HTTP message(?:, including checks against (\d+|nnn) header fields)?\."
    replacement = f"httplint can report on {note_count} different aspects of your HTTP message, including checks against {field_count} header fields."
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(readme_path, "w") as f:
            f.write(new_content)
        print(f"Updated README.md with note count: {note_count}, field count: {field_count}")
    else:
        print(f"README.md already up to date (note count: {note_count}, field count: {field_count})")

if __name__ == "__main__":
    note_count = get_note_count()
    field_count = get_field_count()
    update_readme(note_count, field_count)
