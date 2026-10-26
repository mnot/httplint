#!/usr/bin/env python3

import argparse
import sys

from .utils import load_catalog, save_catalog, find_po_files, get_lang_from_path


def clear_fuzzy(catalog) -> int:
    """
    Reset every fuzzy entry in the catalog to an empty, untranslated one.

    Blanks the translation (every plural form, if there are several), drops the
    'fuzzy' flag and the previous msgid, so that autotranslate treats the entry as
    missing. Returns the number of entries cleared.
    """
    count = 0
    for message in catalog:
        if not message.id or "fuzzy" not in message.flags:
            continue
        if isinstance(message.string, (tuple, list)):
            message.string = tuple("" for _ in message.string)
        else:
            message.string = ""
        message.flags.discard("fuzzy")
        message.previous_id = ()
        message.previous_context = None
        count += 1
    return count


def clear_fuzzy_file(po_path: str) -> int:
    """Clear fuzzy entries in one PO file, saving it only if something changed."""
    catalog = load_catalog(po_path)
    count = clear_fuzzy(catalog)
    if count:
        save_catalog(po_path, catalog)
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Blank fuzzy translations so that autotranslate redoes them"
    )
    parser.add_argument(
        "--locale_dir", default="httplint/translations", help="Path to locale directory"
    )

    args = parser.parse_args()

    po_files = find_po_files(args.locale_dir)
    if not po_files:
        print(f"No PO files found in {args.locale_dir}")
        sys.exit(0)

    for po_file in po_files:
        lang = get_lang_from_path(po_file)
        count = clear_fuzzy_file(po_file)
        print(f"{lang}: cleared {count} fuzzy entries")


if __name__ == "__main__":
    main()
