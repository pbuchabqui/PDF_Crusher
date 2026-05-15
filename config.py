"""Shared configuration and pipeline settings with pydantic-settings support."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Constants
GROQ_CHUNK_CHARS = 30_000
CLAUDE_CONTEXT_CHARS = 180_000
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT_SECONDS = 60
GROQ_MAX_RETRIES = 3

# Groq API key pattern (gsk_...)
GROQ_API_KEY_PATTERN = re.compile(r"^gsk_[A-Za-z0-9]{20,}$")


class OutputFormat(str, Enum):
    """Supported output formats for export."""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    TXT = "txt"


class Language(str, Enum):
    """Supported languages for processing."""
    PT_BR = "pt-BR"
    EN = "en"
    ES = "es"


class DataResidency(str, Enum):
    """Data residency options for compliance."""
    BRAZIL = "brazil"
    US = "us"
    EU = "eu"


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


class Settings(BaseSettings):
    """Application settings with environment variable support.
    
    Settings can be configured via:
    1. Environment variables (e.g., PDF_CRUSHER_GROQ_API_KEY)
    2. .env file
    3. Command-line arguments
    
    Example .env file:
        PDF_CRUSHER_GROQ_API_KEY=gsk_...
        PDF_CRUSHER_OUTPUT_FORMAT=markdown
        PDF_CRUSHER_DATA_RESIDENCY=brazil
        PDF_CRUSHER_RETENTION_DAYS=90
    """
    
    model_config = SettingsConfigDict(
        env_prefix="PDF_CRUSHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Groq Configuration
    groq_api_key: str | None = Field(
        default=None,
        description="Groq API key for name anonymization",
    )
    groq_model: str = Field(
        default=GROQ_DEFAULT_MODEL,
        description="Groq model to use for anonymization",
    )
    groq_timeout: int = Field(
        default=GROQ_TIMEOUT_SECONDS,
        ge=10,
        le=300,
        description="Timeout in seconds for Groq API calls",
    )
    groq_max_retries: int = Field(
        default=GROQ_MAX_RETRIES,
        ge=1,
        le=10,
        description="Maximum number of retries for Groq API calls",
    )
    
    # Processing Configuration
    groq_chunk_chars: int = Field(
        default=GROQ_CHUNK_CHARS,
        ge=1000,
        le=100000,
        description="Maximum characters per chunk for Groq processing",
    )
    claude_context_chars: int = Field(
        default=CLAUDE_CONTEXT_CHARS,
        ge=10000,
        le=500000,
        description="Maximum characters per Claude context file",
    )
    
    # Output Configuration
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format for exported files",
    )
    output_directory: Path = Field(
        default=Path("outputs"),
        description="Default output directory for processed files",
    )
    
    # Language and Localization
    language: Language = Field(
        default=Language.PT_BR,
        description="Primary language for processing and output",
    )
    
    # Compliance and Security
    data_residency: DataResidency = Field(
        default=DataResidency.BRAZIL,
        description="Data residency requirement for compliance",
    )
    retention_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Number of days to retain processed data (None for indefinite)",
    )
    enable_audit_log: bool = Field(
        default=True,
        description="Enable detailed audit logging",
    )
    
    # Feature Flags
    enable_ocr: bool = Field(
        default=False,
        description="Enable OCR for scanned documents",
    )
    enable_table_extraction: bool = Field(
        default=False,
        description="Enable table extraction to CSV/Excel",
    )
    enable_version_tracking: bool = Field(
        default=True,
        description="Enable version tracking in output files",
    )
    
    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v: str | None) -> str | None:
        """Validate Groq API key format."""
        if v is None:
            return None
        if not GROQ_API_KEY_PATTERN.match(v):
            raise ValueError(
                "Invalid Groq API key format. Expected format: gsk_XXXXXXXXXXXXXXXXXXXX"
            )
        return v
    
    @model_validator(mode="after")
    def validate_consistency(self) -> "Settings":
        """Validate configuration consistency."""
        if self.groq_chunk_chars >= self.claude_context_chars:
            raise ValueError(
                f"groq_chunk_chars ({self.groq_chunk_chars}) must be less than "
                f"claude_context_chars ({self.claude_context_chars})"
            )
        return self
    
    def to_pipeline_config(self, use_groq: bool = False) -> PipelineConfig:
        """Convert Settings to PipelineConfig for backwards compatibility."""
        return PipelineConfig(
            use_groq=use_groq,
            groq_api_key=self.groq_api_key if use_groq else None,
            groq_model=self.groq_model,
            groq_chunk_chars=self.groq_chunk_chars,
            claude_context_chars=self.claude_context_chars,
        )


# Application version
__version__ = "1.0.0"
VERSION_INFO = {
    "version": __version__,
    "python_requires": ">=3.10",
    "features": {
        "ocr": False,
        "table_extraction": False,
        "multi_language": True,
        "lgpd_compliance": True,
    }
}
