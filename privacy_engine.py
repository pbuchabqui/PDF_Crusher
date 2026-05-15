"""Local deterministic masking for structured personal data with enhanced PII patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MaskResult:
    text: str
    counts: dict[str, int]


# Enhanced Patterns for Brazilian PII detection
# Patterns are ordered by specificity. Each entry: (regex, replacement_tag).
#
# cpf:      123.456.789-10  or  12345678910  (11 digits with optional punctuation)
# cnpj:     12.345.678/0001-90  or  12345678000190  (14 digits with optional punctuation)
# email:    user@domain.tld
# telefone: requires DDD in parentheses OR country code +55, followed by 8-9 digits with
#           a mandatory separator (hyphen or space) to avoid matching bare numeric sequences
#           such as page numbers or monetary values.
# rg:       RG formats (SSP/SP, DETRAN, etc.) - varies by state
# cnh:      Carteira Nacional de Habilitação (new and old formats)
# pis_pasep: PIS/PASEP/NIT number
PATTERNS: dict[str, tuple[str, str]] = {
    # CPF - Brazilian individual taxpayer registry
    "cpf": (
        r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "[CPF_ANONIMIZADO]",
    ),
    # CNPJ - Brazilian company tax ID
    "cnpj": (
        r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        "[CNPJ_ANONIMIZADO]",
    ),
    # Email addresses
    "email": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL_ANONIMIZADO]",
    ),
    # Phone numbers - Brazilian format with strict requirements
    "telefone": (
        r"(?:"
        r"\+?55\s*\(?\d{2}\)?\s*(?:9\s*)?\d{4}[-\s]\d{4}"  # +55 (DDD) 9XXXX-XXXX
        r"|"
        r"\(\d{2}\)\s*(?:9\s*)?\d{4}[-\s]\d{4}"  # (DDD) 9XXXX-XXXX
        r")\b",
        "[TELEFONE_ANONIMIZADO]",
    ),
    # RG - Brazilian identity document (multiple formats)
    "rg": (
        r"\b(?:RG|Registro Geral)[:\s]*"
        r"(?:\d{1,2}[\.\/-]?\d{3}[\.\/-]?\d{3}[\.\/-]?[A-Z0-9]"
        r"|\d{7,9}[A-Z]?"
        r"|\d{2}\.?\d{3}\.?\d{3}-[A-Z0-9])\b",
        "[RG_ANONIMIZADO]",
    ),
    # CNH - National Driver's License (new format: 11 digits, old: 9-11)
    "cnh": (
        r"\b(?:CNH|Carteira Nacional de Habilitação)[:\s]*"
        r"(?:\d{11}|\d{9,10})\b",
        "[CNH_ANONIMIZADA]",
    ),
    # PIS/PASEP/NIT - Social integration number
    "pis_pasep": (
        r"\b(?:PIS|PASEP|NIT)[:\s]*"
        r"(?:\d{3}\.?\d{5}\.?\d{2}-?\d{1}|\d{11,12})\b",
        "[PIS_PASEP_ANONIMIZADO]",
    ),
    # Process number (Brazilian legal process)
    "numero_processo": (
        r"\b\d{7}-\d{2}\.\d{4}\.\w{3}\.\w{4}\.\d{4}\b",
        "[PROCESSO_ANONIMIZADO]",
    ),
    # CEP - Brazilian postal code
    "cep": (
        r"\b\d{5}-?\d{3}\b",
        "[CEP_ANONIMIZADO]",
    ),
    # Date of birth pattern (common formats)
    "data_nascimento": (
        r"\b(?:nascido? em|nascida? em|data de nascimento)[:\s]*"
        r"(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
        r"|\d{1,2} de \w+ de \d{4})\b",
        "[DATA_NASCIMENTO_ANONIMIZADA]",
    ),
    # Bank account (simplified pattern)
    "conta_bancaria": (
        r"\b(?:conta[:\s]*(?:corrente|poupança)?[:\s]*)?"
        r"(?:\d{4,6}[-/]\d{1,4}[-/]\d{1,4}|\d{8,14})\b",
        "[CONTA_BANCARIA_ANONIMIZADA]",
    ),
}


def mask_structured_data(text: str) -> MaskResult:
    """Mask structured personal data in text using regex patterns.
    
    Args:
        text: Input text to mask
        
    Returns:
        MaskResult with masked text and counts per pattern type
        
    Example:
        >>> result = mask_structured_data("CPF: 123.456.789-10")
        >>> result.text
        'CPF: [CPF_ANONIMIZADO]'
        >>> result.counts['cpf']
        1
    """
    masked = text or ""
    counts: dict[str, int] = {}

    for name, (pattern, tag) in PATTERNS.items():
        masked, count = re.subn(pattern, tag, masked, flags=re.IGNORECASE)
        counts[name] = count

    return MaskResult(masked, counts)
