"""Application configuration read from the environment.

All values are read from environment variables with sensible defaults. No
secrets, endpoints, or model ids are hard-coded in the source (per the
architecture and coding-standards steering); the defaults here are safe,
non-secret placeholders that a real deployment overrides via the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Environment variable names (single source of truth).
ENV_DB_PATH = "KIROOPS_DB_PATH"
ENV_LLM_MODEL_ID = "KIROOPS_LLM_MODEL_ID"
ENV_LLM_ENDPOINT = "KIROOPS_LLM_ENDPOINT"

# Non-secret defaults used when the environment does not provide a value.
DEFAULT_DB_PATH = "kiroops.db"
DEFAULT_LLM_MODEL_ID = "anthropic.claude-3-5-sonnet"
DEFAULT_LLM_ENDPOINT = "https://bedrock-runtime.us-east-1.amazonaws.com"

# Sentinel value selecting an in-memory SQLite database (used by tests).
IN_MEMORY_DB_PATH = ":memory:"


@dataclass(frozen=True)
class LlmConfig:
    """Configuration for the LLM provider boundary (Req 4.6).

    The model identifier and endpoint are supplied through configuration so the
    diagnosis agent uses the configured values rather than hard-coded ones.
    """

    model_id: str
    endpoint: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "LlmConfig":
        """Build an ``LlmConfig`` from environment variables (with defaults)."""
        source = os.environ if env is None else env
        return cls(
            model_id=source.get(ENV_LLM_MODEL_ID, DEFAULT_LLM_MODEL_ID),
            endpoint=source.get(ENV_LLM_ENDPOINT, DEFAULT_LLM_ENDPOINT),
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    db_path: str
    llm: LlmConfig

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AppConfig":
        """Build an ``AppConfig`` from environment variables (with defaults)."""
        source = os.environ if env is None else env
        return cls(
            db_path=source.get(ENV_DB_PATH, DEFAULT_DB_PATH),
            llm=LlmConfig.from_env(source),
        )


def get_db_path(env: dict[str, str] | None = None) -> str:
    """Return the configured SQLite database path (default ``kiroops.db``)."""
    source = os.environ if env is None else env
    return source.get(ENV_DB_PATH, DEFAULT_DB_PATH)
