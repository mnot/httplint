import io
import unittest
from typing import Any, List, Optional, Tuple

from tools.i18n.extractors import extract_notes, keyword_names

SOURCE = b"""
L_("with local keyword")
translate("with other keyword")
_("with default keyword")
ignored("not a keyword")
"""

# The shapes Babel has used for the per-section 'keywords' option in babel.cfg:
# the raw string (< 2.18) and a dict of parsed keywords (>= 2.18); a list is
# what extract_notes used to accept for any other caller.
SHAPES = {
    "str": "L_ translate",
    "dict": {"L_": None, "translate": None},
    "list": ["L_", "translate"],
    "tuple": ("L_", "translate"),
}

Result = List[Tuple[int, Optional[str], Any, List[str]]]


def run_extractor(keywords_option: Any) -> Result:
    # Babel passes the global keywords (here, "_") positionally.
    return list(
        extract_notes(
            io.BytesIO(SOURCE),
            ["_"],
            [],
            {"keywords": keywords_option},
        )
    )


class TestExtractorKeywords(unittest.TestCase):
    def test_keyword_names(self) -> None:
        for name, shape in SHAPES.items():
            with self.subTest(shape=name):
                self.assertEqual(keyword_names(shape), ["L_", "translate"])

    def test_keyword_names_empty(self) -> None:
        for empty in (None, "", {}, []):
            with self.subTest(empty=empty):
                self.assertEqual(keyword_names(empty), [])

    def test_extra_keywords_extracted(self) -> None:
        for name, shape in SHAPES.items():
            with self.subTest(shape=name):
                self.assertEqual(
                    [
                        (lineno, funcname, messages)
                        for lineno, funcname, messages, _ in run_extractor(shape)
                    ],
                    [
                        (2, None, "with local keyword"),
                        (3, None, "with other keyword"),
                        (4, "_", "with default keyword"),
                    ],
                )

    def test_shapes_agree(self) -> None:
        expected = run_extractor(SHAPES["str"])
        for name, shape in SHAPES.items():
            with self.subTest(shape=name):
                self.assertEqual(run_extractor(shape), expected)

    def test_no_keywords_option(self) -> None:
        results = list(extract_notes(io.BytesIO(SOURCE), ["_"], [], {}))
        self.assertEqual([r[2] for r in results], ["with default keyword"])


if __name__ == "__main__":
    unittest.main()
