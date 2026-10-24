"""
httplint.field.utils used to hold every field helper; it now re-exports them from the module
for their theme. Anything that was importable from it must stay importable (REDbot and other
external code do this), as the very same object.
"""

import importlib
import unittest
from typing import Dict, List

from httplint.field import utils

HOMES: Dict[str, List[str]] = {
    "common": ["RE_FLAGS", "syntax_position"],
    "conneg": ["BAD_Q_VALUE", "parse_qvalue", "vary_covers"],
    "delta_seconds": ["is_negative_integer", "parse_delta_seconds", "parse_digits"],
    "entity_tag": [
        "ENTITY_TAG_LIST_STAR",
        "ENTITY_TAG_WEAK_CASE",
        "is_entity_tag",
        "parse_entity_tag",
    ],
    "http_date": ["BAD_DATE_SYNTAX", "DATE_OBSOLETE", "parse_http_date"],
    "list_split": ["_QDTEXT", "_QUOTED_PAIR_CHAR", "split_list_field"],
    "media_type": [
        "MEDIA_TYPE_BAD_NAME",
        "MEDIA_TYPE_LONG_NAME",
        "RESTRICTED_NAME_UNBOUNDED",
        "check_media_type",
        "parse_media_type",
        "parse_media_type_once",
    ],
    "params": [
        "PARAM_REPEATS",
        "PARAM_SINGLE_QUOTED",
        "PARAM_STAR_BAD",
        "PARAM_STAR_CHARSET",
        "PARAM_STAR_ERROR",
        "PARAM_STAR_NOCHARSET",
        "PARAM_STAR_QUOTED",
        "parse_params",
        "split_params",
        "split_string",
        "unquote_string",
    ],
    "reporting": ["known_reporting_endpoints", "report_to_groups"],
    "sf_helpers": [
        "check_sf_item_token",
        "check_sf_params",
        "is_integer",
        "is_number",
        "sf_type_matches",
    ],
    "urls": ["is_secure", "resolve_url"],
}


class UtilsCompatTest(unittest.TestCase):
    def test_same_objects(self) -> None:
        for module_name, names in HOMES.items():
            module = importlib.import_module(f"httplint.field.{module_name}")
            for name in names:
                with self.subTest(name=name):
                    self.assertIs(getattr(utils, name), getattr(module, name))

    def test_all_matches(self) -> None:
        expected = {name for names in HOMES.values() for name in names}
        self.assertEqual(set(utils.__all__), expected)

    def test_redbot_import(self) -> None:
        # redbot/resource/link_parse.py
        # pylint: disable=import-outside-toplevel
        from httplint.field.utils import split_params, unquote_string

        self.assertEqual(split_params("a=b; c=d"), ["a=b", "c=d"])
        self.assertEqual(unquote_string('"x"'), "x")


if __name__ == "__main__":
    unittest.main()
