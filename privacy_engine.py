"""Local deterministic masking for structured personal data."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MaskResult:
    text: str
    counts: dict[str, int]


PATTERNS: dict[str, tuple[str, str]] = {
    "cpf": (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF_ANONIMIZADO]"),
    "cnpj": (r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", "[CNPJ_ANONIMIZADO]"),
    "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_ANONIMIZADO]"),
    "telefone": (
        r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9\s*)?\d{4}[-\s]?\d{4}\b",
        "[TELEFONE_ANONIMIZADO]",
    ),
}


def mask_structured_data(text: str) -> MaskResult:
    masked = text or ""
    counts: dict[str, int] = {}

    for name, (pattern, tag) in PATTERNS.items():
        masked, count = re.subn(pattern, tag, masked)
        counts[name] = count

    return MaskResult(masked, counts)
