import unittest
from unittest.mock import patch
from aimes_cli.cli import interactive_wizard

class WizardTests(unittest.TestCase):
    def test_main_menu_exit(self):
        with patch('builtins.input', side_effect=['0']):
            self.assertEqual(interactive_wizard(), 0)

    def test_invalid_menu_choice_then_exit(self):
        with patch('builtins.input', side_effect=['99', '0']):
            self.assertEqual(interactive_wizard(), 0)

if __name__ == '__main__':
    unittest.main()
