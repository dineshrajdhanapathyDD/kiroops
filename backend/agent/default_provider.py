"""Default LLM provider selection for the wired app (Tasks 10.5, 12.1).

The production app needs a safe default provider that is built from
:class:`backend.config.LlmConfig` (so it carries the configured model id,
endpoint, and region per Req 4.6). Two implementations exist:

- :class:`UnavailableLlmProvider` - always raises
  :class:`~backend.agent.provider.LlmUnavailableError` on ``complete``. This is
  the safe fallback (and the historical default) used when Bedrock is not
  selected or ``boto3`` is not installed.
- :class:`~backend.agent.bedrock_provider.BedrockNovaProvider` - the real
  Amazon Bedrock Nova provider (Task 12).

:func:`build_default_provider` prefers the Bedrock provider when it can be
constructed (``boto3`` importable), and otherwise falls back to the
always-unavailable provider. Construction is lazy and never contacts AWS or
requires credentials, so the app factory and every existing test build without
Bedrock access; a real call only happens (and only fails as
``LlmUnavailableError``) at ``complete`` time. The provider stays injectable via
``create_app(llm=...)``, so tests keep substituting their own stubs.

Requirements: 4.2, 4.5, 4.6.
"""

from __future__ import annotations

from backend.agent.provider import LlmProvider, LlmResult, LlmUnavailableError
from backend.config import LlmConfig


class UnavailableLlmProvider:
    """A configured :class:`LlmProvider` that is always unavailable (Req 4.5).

    Holds the configured model id/endpoint (Req 4.6) so the wiring reflects
    configuration even though no model is contacted.
    """

    def __init__(self, config: LlmConfig) -> None:
        self._config = config

    @property
    def config(self) -> LlmConfig:
        """The configuration this provider was built from."""
        return self._config

    def complete(self, prompt: str) -> LlmResult:
        """Always raise :class:`LlmUnavailableError` (no real model configured)."""
        raise LlmUnavailableError(
            "No LLM provider is configured "
            f"(model_id={self._config.model_id!r}); diagnosis is unavailable."
        )


def build_default_provider(config: LlmConfig | None = None) -> LlmProvider:
    """Build the default provider from configuration (or the env default).

    Prefers the real Bedrock Nova provider when ``boto3`` is available, so a
    deployment with the optional ``bedrock`` extra installed and valid AWS
    credentials returns live diagnoses. When ``boto3`` is not installed the
    always-unavailable provider is returned, keeping the out-of-the-box
    "diagnosis unavailable -> 503, status unchanged" behavior (Req 4.5).

    Construction is lazy and safe: it never contacts AWS. The Bedrock client is
    created on the first ``complete`` call, and any failure there (missing
    credentials, network, service error) surfaces as
    :class:`LlmUnavailableError` rather than at app-construction time.
    """
    resolved = config if config is not None else LlmConfig.from_env()

    try:
        import boto3  # noqa: F401, PLC0415 (probe only; import is optional)
    except ImportError:
        return UnavailableLlmProvider(resolved)

    # boto3 is available: use the real provider. Import here to avoid importing
    # the Bedrock module (and its typing on boto3) when the extra is absent.
    from backend.agent.bedrock_provider import BedrockNovaProvider

    return BedrockNovaProvider(resolved)
