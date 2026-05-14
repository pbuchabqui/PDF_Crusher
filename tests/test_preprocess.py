import sys
import unittest

# Skip the entire module if heavy PDF dependencies are not available.
try:
    from preprocess import (
        _confidence,
        _global_confidence,
        _has_any,
        _possible_types,
        LABEL_DECISION,
        LABEL_PETITION,
        LABEL_LABOR,
        DECISION_TERMS,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "pypdf/docling not installed — skipping preprocess tests")
class TestHasAny(unittest.TestCase):
    def test_matches_upper(self):
        self.assertTrue(_has_any("SENTENÇA proferida", DECISION_TERMS))

    def test_matches_lower_input(self):
        self.assertTrue(_has_any("sentença proferida", DECISION_TERMS))

    def test_no_match(self):
        self.assertFalse(_has_any("texto qualquer sem termos", DECISION_TERMS))

    def test_empty_text(self):
        self.assertFalse(_has_any("", DECISION_TERMS))

    def test_empty_terms(self):
        self.assertFalse(_has_any("SENTENÇA", []))


@unittest.skipUnless(HAS_DEPS, "pypdf/docling not installed — skipping preprocess tests")
class TestConfidence(unittest.TestCase):
    def test_alto(self):
        self.assertEqual(_confidence("x" * 500), "ALTO")

    def test_medio(self):
        self.assertEqual(_confidence("x" * 100), "MÉDIO")

    def test_baixo(self):
        self.assertEqual(_confidence("x"), "BAIXO")

    def test_critico(self):
        self.assertEqual(_confidence(""), "CRÍTICO")

    def test_critico_whitespace_only(self):
        self.assertEqual(_confidence("   "), "CRÍTICO")


@unittest.skipUnless(HAS_DEPS, "pypdf/docling not installed — skipping preprocess tests")
class TestGlobalConfidence(unittest.TestCase):
    def test_all_alto(self):
        self.assertEqual(_global_confidence(["ALTO", "ALTO", "ALTO"]), "ALTO")

    def test_majority_critico(self):
        result = _global_confidence(["CRÍTICO"] * 6 + ["ALTO"] * 4)
        self.assertEqual(result, "CRÍTICO")

    def test_some_weak(self):
        result = _global_confidence(["ALTO"] * 3 + ["BAIXO"])
        self.assertEqual(result, "BAIXO")

    def test_empty_list(self):
        result = _global_confidence([])
        self.assertIn(result, {"ALTO", "MÉDIO", "BAIXO", "CRÍTICO"})


@unittest.skipUnless(HAS_DEPS, "pypdf/docling not installed — skipping preprocess tests")
class TestPossibleTypes(unittest.TestCase):
    def test_decision_detected(self):
        labels = _possible_types("O juiz JULGO procedente o pedido.")
        self.assertIn(LABEL_DECISION, labels)

    def test_petition_detected(self):
        labels = _possible_types("PETIÇÃO inicial apresentada.")
        self.assertIn(LABEL_PETITION, labels)

    def test_labor_detected(self):
        labels = _possible_types("HOLERITE do empregado referente ao mês.")
        self.assertIn(LABEL_LABOR, labels)

    def test_empty_text(self):
        labels = _possible_types("")
        self.assertEqual(labels, [])

    def test_multiple_types(self):
        labels = _possible_types("SENTENÇA e PETIÇÃO no mesmo texto")
        self.assertIn(LABEL_DECISION, labels)
        self.assertIn(LABEL_PETITION, labels)


class TestConfig(unittest.TestCase):
    """PipelineConfig validation (no heavy deps required)."""

    def test_valid_config(self):
        from config import PipelineConfig
        cfg = PipelineConfig()
        cfg.validate()

    def test_groq_without_key_raises(self):
        from config import PipelineConfig
        cfg = PipelineConfig(use_groq=True, groq_api_key=None)
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_invalid_chunk_size_raises(self):
        from config import PipelineConfig
        cfg = PipelineConfig(groq_chunk_chars=0)
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_invalid_context_size_raises(self):
        from config import PipelineConfig
        cfg = PipelineConfig(claude_context_chars=-1)
        with self.assertRaises(ValueError):
            cfg.validate()


if __name__ == "__main__":
    unittest.main()
