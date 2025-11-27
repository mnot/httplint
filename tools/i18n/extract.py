import argparse
import json
import os
import sys
from .utils import load_catalog, find_po_files


def extract_file(po_file, json_file, lang):
    catalog = load_catalog(po_file)
    all_translations = {}

    if os.path.exists(json_file):
        with open(json_file, "r") as f:
            try:
                all_translations = json.load(f)
            except json.JSONDecodeError:
                pass

    if lang not in all_translations:
        all_translations[lang] = {}

    translations = all_translations[lang]

    count = 0
    for message in catalog:
        if message.id and message.string:
            translations[message.id] = message.string
            count += 1

    with open(json_file, "w") as f:
        json.dump(all_translations, f, indent=2, sort_keys=True, ensure_ascii=False)

    print(f"Extracted {count} translations for '{lang}' to {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract translations from PO to JSON")
    parser.add_argument("--po_file", help="Path to a single PO file")
    parser.add_argument(
        "--locale_dir", help="Path to locale directory (process all locales)"
    )
    parser.add_argument(
        "--json_file",
        default="tools/i18n/data/translations.json",
        help="Path to JSON file",
    )
    parser.add_argument("--lang", help="Language code (required for single file)")

    args = parser.parse_args()

    if args.locale_dir:
        po_files = find_po_files(args.locale_dir)
        if not po_files:
            print(f"No PO files found in {args.locale_dir}")
            sys.exit(0)
        for po_file in po_files:
            # Derive lang from path
            # Assuming structure .../locale/LC_MESSAGES/messages.po
            # We can use get_lang_from_path from utils if available, but it wasn't imported in previous view.
            # Let's check imports. from .utils import load_catalog, find_po_files
            # I should import get_lang_from_path.
            from .utils import get_lang_from_path

            lang = get_lang_from_path(po_file)
            if not lang:
                print(f"Skipping {po_file}: could not determine language")
                continue

            print(f"Processing {po_file} ({lang})...")
            extract_file(po_file, args.json_file, lang)
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file extraction")
            sys.exit(1)
        extract_file(args.po_file, args.json_file, args.lang)
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
