"""Shared configuration and pipeline settings."""

from __future__ import annotations

from dataclasses import dataclass, field


GROQ_CHUNK_CHARS = 30_000
CLAUDE_CONTEXT_CHARS = 180_000
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT_SECONDS = 60
GROQ_MAX_RETRIES = 3


@dataclass
class PipelineConfig:
    use_groq: bool = False
    groq_api_key: str | None = None
    groq_model: str = GROQ_DEFAULT_MODEL
    groq_chunk_chars: int = GROQ_CHUNK_CHARS
    claude_context_chars: int = CLAUDE_CONTEXT_CHARS
    # Reserved for future options (e.g. force_ocr, table_extraction)
    extra: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.use_groq and not self.groq_api_key:
            raise ValueError("groq_api_key is required when use_groq=True")
        if self.groq_chunk_chars <= 0:
            raise ValueError("groq_chunk_chars must be positive")
        if self.claude_context_chars <= 0:
            raise ValueError("claude_context_chars must be positive")
