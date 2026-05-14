"""Optional name anonymization through Groq with retry and timeout."""

from __future__ import annotations

import logging
import time

from groq import Groq, APIError, APITimeoutError, RateLimitError

from config import GROQ_DEFAULT_MODEL, GROQ_MAX_RETRIES, GROQ_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um higienizador de dados pessoais para textos jurídicos brasileiros em português brasileiro.
Substitua apenas nomes de pessoas físicas por [NOME_ANONIMIZADO].
Inclua partes, advogados, testemunhas, peritos, magistrados, servidores, delegados, promotores e defensores.
Não altere números de páginas, IDs, valores, datas, formatação Markdown, citações legais ou sentido do texto.
Responda somente com o texto higienizado."""


def anonymize_names(
    text: str,
    api_key: str,
    model: str = GROQ_DEFAULT_MODEL,
    max_retries: int = GROQ_MAX_RETRIES,
    timeout: int = GROQ_TIMEOUT_SECONDS,
) -> str:
    """Send text to Groq for name anonymization with exponential-backoff retry."""
    client = Groq(api_key=api_key, timeout=timeout)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            result = response.choices[0].message.content or ""
            logger.info("Groq anonymization succeeded on attempt %d.", attempt)
            return result

        except RateLimitError as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("Groq rate-limited (attempt %d/%d). Retrying in %ds.", attempt, max_retries, wait)
            time.sleep(wait)

        except APITimeoutError as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("Groq timeout (attempt %d/%d). Retrying in %ds.", attempt, max_retries, wait)
            time.sleep(wait)

        except APIError as exc:
            last_exc = exc
            logger.error("Groq API error (attempt %d/%d): %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Groq anonymization failed after {max_retries} attempts.") from last_exc
