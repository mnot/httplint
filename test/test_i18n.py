import unittest
from datetime import timedelta
import time

from httplint.i18n import set_locale, translate, ngettext, format_timedelta

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


if __name__ == "__main__":
    unittest.main()
