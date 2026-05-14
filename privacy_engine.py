"""Local deterministic masking for structured personal data."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MaskResult:
    text: str
    counts: dict[str, int]


# Patterns are ordered by specificity. Each entry: (regex, replacement_tag).
#
# cpf:      123.456.789-10  or  12345678910  (11 digits with optional punctuation)
# cnpj:     12.345.678/0001-90  or  12345678000190  (14 digits with optional punctuation)
# email:    user@domain.tld
# telefone: requires DDD in parentheses OR country code +55, followed by 8-9 digits with
#           a mandatory separator (hyphen or space) to avoid matching bare numeric sequences
#           such as page numbers or monetary values.
PATTERNS: dict[str, tuple[str, str]] = {
    "cpf": (
        r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "[CPF_ANONIMIZADO]",
    ),
    "cnpj": (
        r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        "[CNPJ_ANONIMIZADO]",
    ),
    "email": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL_ANONIMIZADO]",
    ),
    # Requires explicit DDD between parentheses OR +55 prefix to avoid false positives on
    # bare 8-digit numbers (page refs, process numbers, monetary values, etc.).
    "telefone": (
        r"(?:"
        r"\+?55\s*\(?\d{2}\)?\s*(?:9\s*)?\d{4}[-\s]\d{4}"  # +55 (DDD) 9XXXX-XXXX
        r"|"
        r"\(\d{2}\)\s*(?:9\s*)?\d{4}[-\s]\d{4}"  # (DDD) 9XXXX-XXXX
        r")\b",
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
