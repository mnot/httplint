import unittest
from unittest.mock import patch

from httplint.field.description import get_field_description
from httplint.field.parsers.cache_control import cache_control

class TestFieldDescription(unittest.TestCase):
    def test_get_field_description_translation(self):
        """
        Verify that get_field_description calls translate.
        """
        original_description = cache_control.description
        
        with patch("httplint.field.description.translate") as mock_translate:
            mock_translate.side_effect = lambda x: f"Translated: {x}"
            
            desc = get_field_description("Cache-Control")
            
            self.assertTrue(desc.startswith("Translated: "))
            self.assertIn(original_description, desc)
            mock_translate.assert_called_once()

    def test_get_field_description_no_translation(self):
        """
        Verify that get_field_description returns the original string if no translation.
        """
        desc = get_field_description("Cache-Control")
        self.assertEqual(desc, cache_control.description)

if __name__ == "__main__":
    unittest.main()
