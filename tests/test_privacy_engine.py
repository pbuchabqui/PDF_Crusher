import unittest

from privacy_engine import mask_structured_data


class TestPrivacyEngine(unittest.TestCase):
    def test_masks_cpf(self):
        result = mask_structured_data("CPF 123.456.789-10")
        self.assertIn("[CPF_ANONIMIZADO]", result.text)
        self.assertEqual(result.counts["cpf"], 1)

    def test_masks_cpf_no_punctuation(self):
        result = mask_structured_data("CPF 12345678910")
        self.assertIn("[CPF_ANONIMIZADO]", result.text)

    def test_masks_cnpj(self):
        result = mask_structured_data("CNPJ 12.345.678/0001-90")
        self.assertIn("[CNPJ_ANONIMIZADO]", result.text)
        self.assertEqual(result.counts["cnpj"], 1)

    def test_masks_email(self):
        result = mask_structured_data("email a@b.com")
        self.assertIn("[EMAIL_ANONIMIZADO]", result.text)
        self.assertEqual(result.counts["email"], 1)

    def test_masks_phone_with_ddd_parentheses(self):
        result = mask_structured_data("tel (11) 98765-4321")
        self.assertIn("[TELEFONE_ANONIMIZADO]", result.text)
        self.assertEqual(result.counts["telefone"], 1)

    def test_masks_phone_with_country_code(self):
        result = mask_structured_data("+55 11 98765-4321")
        self.assertIn("[TELEFONE_ANONIMIZADO]", result.text)

    def test_does_not_mask_bare_8digit_number(self):
        # Bare 8-digit sequences (page refs, amounts) must NOT be masked
        result = mask_structured_data("ver página 1234 5678 do processo")
        self.assertEqual(result.counts["telefone"], 0)

    def test_empty_string(self):
        result = mask_structured_data("")
        self.assertEqual(result.text, "")
        self.assertEqual(sum(result.counts.values()), 0)

    def test_none_input(self):
        result = mask_structured_data(None)  # type: ignore[arg-type]
        self.assertEqual(result.text, "")

    def test_multiple_cpfs(self):
        result = mask_structured_data("123.456.789-10 e 987.654.321-00")
        self.assertEqual(result.counts["cpf"], 2)

    def test_counts_returned(self):
        result = mask_structured_data("CPF 123.456.789-10 email a@b.com")
        self.assertIn("cpf", result.counts)
        self.assertIn("email", result.counts)


if __name__ == "__main__":
    unittest.main()
