import unittest
from datetime import timedelta
import time

from httplint import i18n
import os
from httplint.i18n import get_locale, set_locale, translate, ngettext, format_timedelta

class TestI18n(unittest.TestCase):
    def test_context_switching(self) -> None:
        # Default is English
        self.assertEqual(translate("ahead"), "ahead")
        
        # Switch to French
        with set_locale("fr"):
            # "ahead" is translated to "en avance"
            self.assertEqual(translate("ahead"), "en avance")
            
        # Should be back to English
        self.assertEqual(translate("ahead"), "ahead")

    def test_format_timedelta(self) -> None:
        delta = timedelta(hours=1)
        
        # English default
        self.assertIn("1 hour", format_timedelta(delta))
        
        # French
        with set_locale("fr"):
            # Babel's default for fr is "1 heure" (possibly with NBSP)
            result = format_timedelta(delta).replace("\xa0", " ")
            self.assertIn("1 heure", result)

    def test_unknown_locale(self) -> None:
        delta = timedelta(hours=1)
        for name in ["xx", "../x", "C", "xx-YY"]:
            with set_locale(name):
                self.assertEqual(get_locale(), "en")
                self.assertEqual(translate("ahead"), "ahead")
                self.assertIn("1 hour", format_timedelta(delta))

    def test_known_locale_kept(self) -> None:
        with set_locale("en_US"):
            self.assertEqual(get_locale(), "en_US")
            self.assertIn("1 hour", format_timedelta(timedelta(hours=1)))

    def test_cache_bounded_by_catalogs(self) -> None:
        shipped = {
            name
            for name in os.listdir(os.path.join(os.path.dirname(i18n.__file__), "translations"))
            if os.path.isdir(os.path.join(os.path.dirname(i18n.__file__), "translations", name))
        }
        for name in ["en_US@a1", "en_US@a2", "en_US.zz", "en_ZZ", "xx", "fr_fr", "FR", "fr_CA"]:
            with set_locale(name):
                translate("ahead")
        self.assertLessEqual(set(i18n._translations_cache), shipped | {""})
        with set_locale("fr_fr"):
            self.assertEqual(translate("ahead"), "en avance")

    def test_hyphenated_locales(self) -> None:
        delta = timedelta(hours=1)
        for name in ["fr-FR", "FR-fr", "fr_FR"]:
            with set_locale(name):
                self.assertEqual(translate("ahead"), "en avance", name)
                self.assertIn("1 heure", format_timedelta(delta).replace("\xa0", " "))
        with set_locale("zh-CN"):
            self.assertEqual(get_locale(), "zh_CN")
            self.assertNotEqual(translate("ahead"), "ahead")
        with set_locale("en-US"):
            self.assertEqual(get_locale(), "en_US")
            self.assertIn("1 hour", format_timedelta(delta))
        with set_locale("xx-YY"):
            self.assertEqual(get_locale(), "en")
        self.assertLessEqual(set(i18n._translations_cache), {"", "es", "fr", "ja", "zh"})


if __name__ == "__main__":
    unittest.main()
