#!/usr/bin/env python3
import sys
import os
import re

# Ensure we can import from the current directory (test/) and the project root
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from httplint.note import Note
from utils import checkSubClasses

def dummy_check(note_cls):
    return 0

def get_note_count():
    paths = ["httplint", "httplint/field", "httplint/field/parsers"]
    count, _ = checkSubClasses(Note, paths, dummy_check)
    return count

def update_readme(count):
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()
    
    # Pattern to match: "httplint can report on nnn different aspects" or "httplint can report on 123 different aspects"
    pattern = r"(httplint can report on )(\d+|nnn)( different aspects)"
    replacement = f"\\g<1>{count}\\g<3>"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(readme_path, "w") as f:
            f.write(new_content)
        print(f"Updated README.md with note count: {count}")
    else:
        print(f"README.md already up to date (count: {count})")

if __name__ == "__main__":
    count = get_note_count()
    update_readme(count)
