import unittest

from omnidoc_worker.cleaning import clean_text


class CleanTextTests(unittest.TestCase):
    def test_drops_blank_lines_and_collapses_whitespace(self) -> None:
        raw = "  Invoice\t  100 \n\n\nVendor   ACME\n\n"
        self.assertEqual(clean_text(raw), "Invoice 100\nVendor ACME")

    def test_removes_consecutive_duplicate_lines_and_control_characters(self) -> None:
        raw = "Total\x00\nTotal\nTotal due\n"
        self.assertEqual(clean_text(raw), "Total\nTotal due")

    def test_empty_input(self) -> None:
        self.assertEqual(clean_text("   \n\n"), "")


if __name__ == "__main__":
    unittest.main()
