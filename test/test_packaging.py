import glob
import os
import re
import unittest

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = os.path.join(os.path.dirname(__file__), "..")
PACKAGE = os.path.join(ROOT, "httplint")


class TestPackaging(unittest.TestCase):
    def setUp(self) -> None:
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            self.config = tomllib.load(fh)

    def test_setuptools_floor(self) -> None:
        # Recursive ** package-data globs need setuptools>=62.3 (older versions silently skip
        # the .mo files); the PEP 639 SPDX `license` string needs >=77.
        requires = self.config["build-system"]["requires"]
        spec = next(r for r in requires if r.startswith("setuptools"))
        match = re.fullmatch(r"setuptools\s*>=\s*(\d+)(?:\.(\d+))?.*", spec)
        assert match, spec
        self.assertGreaterEqual(int(match.group(1)), 77, spec)

    def test_translation_catalogues_are_packaged(self) -> None:
        patterns = self.config["tool"]["setuptools"]["package-data"]["httplint"]
        packaged = {
            os.path.relpath(path, PACKAGE)
            for pattern in patterns
            for path in glob.glob(os.path.join(PACKAGE, pattern), recursive=True)
        }
        locales = [
            entry
            for entry in os.listdir(os.path.join(PACKAGE, "translations"))
            if os.path.isdir(os.path.join(PACKAGE, "translations", entry))
        ]
        self.assertTrue(locales)
        for locale in locales:
            catalogue = os.path.join("translations", locale, "LC_MESSAGES", "messages.mo")
            self.assertTrue(
                os.path.exists(os.path.join(PACKAGE, catalogue)), f"{locale}: no .mo catalogue"
            )
            self.assertIn(catalogue, packaged, f"{locale}: .mo not covered by package-data")
