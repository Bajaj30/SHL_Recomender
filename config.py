"""
Centralised configuration using Pydantic Settings.

All parameters are defined here with sensible defaults.
Override any value via environment variables (prefixed with SHL_)
or through a .env file in the project root.

Paths are stored as relative strings in config but resolved to absolute
paths via the resolve_path() helper, anchored to PROJECT_ROOT
(the directory containing this file).

Examples:
    SHL_EMBEDDING_MODEL=all-mpnet-base-v2
    SHL_TOP_K=10
    SHL_RAW_CATALOG_PATH=data/Catalog.json
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = directory where this config.py lives
PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Project-wide configuration, loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="SHL_",        # all env vars start with SHL_
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",           # silently ignore unknown SHL_* vars
    )

    # --- Embedding / Retriever ---
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 15

    # --- Catalog paths (relative to PROJECT_ROOT) ---
    raw_catalog_path: str = "Catalog.json"
    prepared_catalog_path: str = "catalog_prepared.json"

    # --- Key map (category → single-letter code) ---
    # Kept here so it's visible alongside the rest of the config,
    # but not overridable via env vars (complex nested type).
    key_map: dict[str, str] = {
        "Knowledge & Skills":           "K",
        "Personality & Behavior":       "P",
        "Ability & Aptitude":           "A",
        "Simulations":                  "S",
        "Competencies":                 "C",
        "Biodata & Situational Judgment": "B",
        "Development & 360":            "D",
        "Assessment Exercises":         "E",
    }

    # --- Fallback test_type code when no keys match ---
    default_test_type_code: str = "K"

    # --- LLM / Gemini (Vertex AI with ADC) ---
    gemini_model: str = "gemini-2.5-flash"
    gemini_project: str = "shlassingement"
    gemini_location: str = "us-central1"
    llm_timeout_s: int = 25         # spec hard limit 30s; 5s margin for FastAPI
    llm_temperature: float = 0.1    # low = more consistent JSON output
    llm_max_tokens: int = 4000

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a path relative to PROJECT_ROOT. Already-absolute paths pass through."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return PROJECT_ROOT / p


# Singleton instance — import this everywhere
settings = Settings()
