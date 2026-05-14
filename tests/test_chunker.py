import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker import split_text


class TestChunker(unittest.TestCase):
    def test_split_keeps_content(self):
        text = "abc def ghi"
        chunks = split_text(text, 7)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(c) <= 7 for c in chunks))

    def test_no_split_needed(self):
        text = "short text"
        chunks = split_text(text, 100)
        self.assertEqual(chunks, ["short text"])

    def test_empty_string(self):
        chunks = split_text("", 50)
        self.assertEqual(chunks, [])

    def test_prefers_double_newline_boundary(self):
        text = "paragraph one\n\nparagraph two"
        chunks = split_text(text, 20)
        # First chunk should end at the double newline
        self.assertEqual(chunks[0], "paragraph one")

    def test_splits_at_rightmost_boundary(self):
        # split_text picks the rightmost whitespace (max of space/\n/\n\n positions),
        # so a space after a newline takes precedence over the newline.
        text = "line one\nline two more words"
        chunks = split_text(text, 15)
        # window = "line one\nline t"; rfind(" ")=14 wins over rfind("\n")=8
        self.assertEqual(chunks[0], "line one\nline")

    def test_hard_cut_when_no_whitespace(self):
        text = "a" * 20
        chunks = split_text(text, 10)
        # No whitespace — must hard-cut at max_chars
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 10)
        self.assertEqual("".join(chunks), text)

    def test_invalid_max_chars_raises(self):
        with self.assertRaises(ValueError):
            split_text("text", 0)

    def test_strips_whitespace_from_chunks(self):
        text = "  hello   world  "
        chunks = split_text(text, 100)
        self.assertEqual(chunks[0], "hello   world")

    def test_large_text_chunk_count(self):
        text = "word " * 1000
        chunks = split_text(text, 100)
        self.assertTrue(len(chunks) > 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 100)


if __name__ == "__main__":
    unittest.main()
