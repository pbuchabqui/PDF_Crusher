import unittest
from unittest.mock import patch

from pdf_engine import extract_markdown, extract_markdown_pypdf


class TestPdfEngine(unittest.TestCase):
    def test_extract_markdown_pypdf_formats_pages(self):
        with patch("pdf_engine.extract_page_texts", return_value=["texto um", ""]):
            markdown = extract_markdown_pypdf("dummy.pdf")

        self.assertIn("## Página PDF 0001", markdown)
        self.assertIn("texto um", markdown)
        self.assertIn("## Página PDF 0002", markdown)
        self.assertIn("[Página sem texto extraível por pypdf.]", markdown)

    def test_extract_markdown_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            extract_markdown("dummy.pdf", mode="desconhecido")


if __name__ == "__main__":
    unittest.main()
