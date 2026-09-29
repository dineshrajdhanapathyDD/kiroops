"""Default LLM provider used when no real provider is configured (Task 10.5).

A real Bedrock/Anthropic-backed provider is the optional later Task 12, so the
production app needs a safe, dependency-free default in the meantime. This
provider is built from :class:`backend.config.LlmConfig` (so it carries the
configured model id and endpoint per Req 4.6) and always raises
:class:`~backend.agent.provider.LlmUnavailableError` on ``complete``.

Because the app factory makes the provider injectable, tests substitute a stub
that returns canned output (success path) or raises (unavailable path); no test
depends on this default. The default keeps the wired app well-defined and makes
the "LLM unavailable -> status unchanged" behavior the safe out-of-the-box
default until the real provider lands.

Requirements: 4.5, 4.6.
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
    """Build the default provider from configuration (or the env default)."""
    resolved = config if config is not None else LlmConfig.from_env()
    return UnavailableLlmProvider(resolved)
