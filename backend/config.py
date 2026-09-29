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
ENV_LLM_REGION = "KIROOPS_LLM_REGION"
# Fallback region env vars honored when the KiroOps-specific one is unset, so a
# standard AWS environment (e.g. an instance role) works without extra config.
ENV_AWS_REGION = "AWS_REGION"
ENV_AWS_DEFAULT_REGION = "AWS_DEFAULT_REGION"

# Non-secret defaults used when the environment does not provide a value.
DEFAULT_DB_PATH = "kiroops.db"
# Default to an Amazon Bedrock Nova cross-region inference profile id. Nova
# models require an inference profile for on-demand invocation; the ``us.``
# prefix selects the US cross-region profile. Override via KIROOPS_LLM_MODEL_ID
# to pick nova-micro / nova-lite / nova-pro (e.g. ``us.amazon.nova-pro-v1:0``).
DEFAULT_LLM_MODEL_ID = "us.amazon.nova-lite-v1:0"
DEFAULT_LLM_ENDPOINT = "https://bedrock-runtime.us-east-1.amazonaws.com"
# A Bedrock-supported region used when none is configured in the environment.
DEFAULT_LLM_REGION = "us-east-1"

# Sentinel value selecting an in-memory SQLite database (used by tests).
IN_MEMORY_DB_PATH = ":memory:"


@dataclass(frozen=True)
class LlmConfig:
    """Configuration for the LLM provider boundary (Req 4.6).

    The model identifier and endpoint are supplied through configuration so the
    diagnosis agent uses the configured values rather than hard-coded ones.

    ``region`` is the AWS region a Bedrock-backed provider targets. It is an
    optional field with a default so existing callers that construct
    ``LlmConfig(model_id, endpoint)`` positionally keep working unchanged.
    """

    model_id: str
    endpoint: str
    region: str = DEFAULT_LLM_REGION

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "LlmConfig":
        """Build an ``LlmConfig`` from environment variables (with defaults).

        The region is read from ``KIROOPS_LLM_REGION`` first, then falls back to
        the standard ``AWS_REGION`` / ``AWS_DEFAULT_REGION`` variables, and
        finally the non-secret default, so a normal AWS environment needs no
        KiroOps-specific setting.
        """
        source = os.environ if env is None else env
        region = (
            source.get(ENV_LLM_REGION)
            or source.get(ENV_AWS_REGION)
            or source.get(ENV_AWS_DEFAULT_REGION)
            or DEFAULT_LLM_REGION
        )
        return cls(
            model_id=source.get(ENV_LLM_MODEL_ID, DEFAULT_LLM_MODEL_ID),
            endpoint=source.get(ENV_LLM_ENDPOINT, DEFAULT_LLM_ENDPOINT),
            region=region,
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
