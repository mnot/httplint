import argparse
import json
import os
import sys
from .utils import load_catalog, save_catalog, find_po_files


def apply_file(po_file, json_file, lang):
    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found.")
        return

    with open(json_file, "r") as f:
        try:
            all_translations = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {json_file} is not valid JSON.")
            return

    if lang not in all_translations:
        print(f"No translations found for language '{lang}' in {json_file}")
        return

    translations = all_translations[lang]

    catalog = load_catalog(po_file)
    count = 0

    for message in catalog:
        if message.id in translations:
            if message.string != translations[message.id]:
                message.string = translations[message.id]
                count += 1
            elif not message.string:
                message.string = translations[message.id]
                count += 1

    save_catalog(po_file, catalog)
    print(f"Applied {count} translations to {po_file}")


def main():
    parser = argparse.ArgumentParser(description="Apply translations from JSON to PO")
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
            from .utils import get_lang_from_path

            lang = get_lang_from_path(po_file)
            if not lang:
                print(f"Skipping {po_file}: could not determine language")
                continue

            print(f"Processing {po_file} ({lang})...")
            apply_file(po_file, args.json_file, lang)
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file application")
            sys.exit(1)
        apply_file(args.po_file, args.json_file, args.lang)
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
