#!/usr/bin/env python3

import argparse
import sys

from .check import CatalogChecker, mark_fuzzy
from .clear_fuzzy import clear_fuzzy
from .utils import find_po_files, get_lang_from_path, load_catalog, save_catalog


def clear_flagged(catalog, lang=None):
    """
    Blank every entry the checks flag (see check.py), plus any already fuzzy.

    Returns (flagged, cleared): entries newly flagged, and entries blanked.
    """
    flagged = mark_fuzzy(catalog, CatalogChecker().check_catalog(catalog, lang))
    return flagged, clear_fuzzy(catalog)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blank translations flagged by i18n-check (and fuzzy ones), "
        "discarding their text, so autotranslate redoes them"
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
        catalog = load_catalog(po_file)
        flagged, cleared = clear_flagged(catalog, lang)
        if cleared:
            save_catalog(po_file, catalog)
        print(f"{lang}: flagged {flagged}, cleared {cleared}")


if __name__ == "__main__":
    main()
