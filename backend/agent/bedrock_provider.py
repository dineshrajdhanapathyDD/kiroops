"""Amazon Bedrock (Nova) LLM provider (Task 12.1).

A concrete :class:`~backend.agent.provider.LlmProvider` that reaches a real
Amazon Bedrock model through the Converse API. It is the production
implementation of the otherwise-abstract provider boundary; the deterministic
diagnosis core is unchanged and still depends only on the ``LlmProvider``
Protocol, so every existing test keeps injecting its own stub.

Design notes:

- **Nova via Converse.** We call ``bedrock-runtime.converse`` with the model id
  from :class:`~backend.config.LlmConfig` (default a Nova cross-region
  inference profile, e.g. ``us.amazon.nova-lite-v1:0``). Override the model id
  via ``KIROOPS_LLM_MODEL_ID`` to pick nova-micro / nova-lite / nova-pro. Nova
  requires an inference profile for on-demand invocation; the ``us.`` prefix
  selects the US cross-region profile.
- **maxTokens is always set.** Per Bedrock best practice an explicit
  ``maxTokens`` is passed on every call rather than relying on a service
  default.
- **Optional dependency.** ``boto3`` is imported lazily (inside methods) so the
  backend and its tests run without ``boto3`` installed. Install it with the
  optional extra: ``pip install -e ".[bedrock]"``.
- **Credentials.** No credentials are hard-coded; the default AWS credential
  chain (environment, shared config/profile, or an attached role) is used.
- **Graceful failure (Property 6).** Any failure to import ``boto3`` or to
  reach/use the model is wrapped as
  :class:`~backend.agent.provider.LlmUnavailableError`, so the agent's existing
  ``DiagnosisUnavailable`` path and the API's 503 behavior keep working and the
  incident status is left unchanged.

Requirements: 4.2, 4.5, 4.6.
"""

from __future__ import annotations

from typing import Any

from backend.agent.provider import LlmResult, LlmUnavailableError
from backend.config import LlmConfig

# An explicit, sane token budget for a diagnosis completion. Always sent to
# Bedrock (never rely on a service-side default).
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.2


class BedrockNovaProvider:
    """LLM provider backed by Amazon Bedrock Nova via the Converse API.

    Implements the :class:`~backend.agent.provider.LlmProvider` Protocol. The
    boto3 client is created lazily on first use so importing this module and
    constructing the provider never require ``boto3`` or AWS credentials; only
    :meth:`complete` touches the network, and any failure there raises
    :class:`LlmUnavailableError`.
    """

    def __init__(
        self,
        config: LlmConfig,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        client: Any | None = None,
    ) -> None:
        self._config = config
        self._max_tokens = max_tokens
        self._temperature = temperature
        # Optional pre-built client (used by tests to inject a fake transport).
        self._client = client

    @property
    def config(self) -> LlmConfig:
        """The configuration this provider was built from (Req 4.6)."""
        return self._config

    def _get_client(self) -> Any:
        """Return the Bedrock runtime client, creating it lazily on first use.

        Imports ``boto3`` inside the function so the dependency stays optional.
        Any failure (missing boto3, bad config, credential resolution) is
        surfaced to the caller and wrapped as ``LlmUnavailableError``.
        """
        if self._client is not None:
            return self._client

        try:
            import boto3  # noqa: PLC0415 (intentional lazy, optional import)
            from botocore.config import Config  # noqa: PLC0415
        except ImportError as exc:  # boto3 not installed
            raise LlmUnavailableError(
                "boto3 is not installed; install the optional 'bedrock' extra "
                "to enable live diagnosis (pip install -e \".[bedrock]\")."
            ) from exc

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=self._config.region,
            config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
        )
        return self._client

    def complete(self, prompt: str) -> LlmResult:
        """Complete ``prompt`` via Bedrock Converse and return an ``LlmResult``.

        Raises :class:`LlmUnavailableError` on any failure to reach or use the
        model (missing boto3, credentials, network/service errors, throttling,
        timeouts, or a malformed response), preserving Property 6.
        """
        client = self._get_client()

        try:
            response = client.converse(
                modelId=self._config.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": self._max_tokens,
                    "temperature": self._temperature,
                },
            )
        except LlmUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport/service failure
            # Covers botocore ClientError, EndpointConnectionError, BotoCoreError,
            # NoCredentialsError, throttling and read timeouts, etc. The provider
            # boundary always fails as "unavailable" so the agent degrades
            # gracefully (Req 4.5).
            raise LlmUnavailableError(
                f"Bedrock Converse call failed for model "
                f"{self._config.model_id!r} in region {self._config.region!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        text = self._extract_text(response)
        return LlmResult(text=text)

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        """Pull the assistant text out of a Converse response.

        Expected shape: ``response["output"]["message"]["content"][0]["text"]``.
        A missing/malformed shape raises ``LlmUnavailableError`` rather than a
        raw ``KeyError`` so callers only ever handle one failure type.
        """
        try:
            return response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmUnavailableError(
                f"Bedrock Converse response was malformed: {type(exc).__name__}: {exc}"
            ) from exc


def build_bedrock_provider(config: LlmConfig | None = None) -> BedrockNovaProvider:
    """Build a :class:`BedrockNovaProvider` from configuration (or the env).

    Construction never contacts AWS or requires ``boto3``; the client is created
    lazily on the first :meth:`BedrockNovaProvider.complete` call.
    """
    resolved = config if config is not None else LlmConfig.from_env()
    return BedrockNovaProvider(resolved)
