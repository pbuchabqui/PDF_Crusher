import unittest

from chunker import split_text


class TestChunker(unittest.TestCase):
    def test_split_text_keeps_content(self):
        text = "abc def ghi"
        chunks = split_text(text, 7)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(c) <= 7 for c in chunks))


if __name__ == "__main__":
    unittest.main()
