import unittest

from privacy_engine import mask_structured_data


class TestPrivacyEngine(unittest.TestCase):
    def test_masks_structured_data(self):
        result = mask_structured_data("CPF 123.456.789-10 email a@b.com")
        self.assertIn("[CPF_ANONIMIZADO]", result.text)
        self.assertIn("[EMAIL_ANONIMIZADO]", result.text)


if __name__ == "__main__":
    unittest.main()
