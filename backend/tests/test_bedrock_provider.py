"""Smoke tests for the Bedrock Nova provider (Task 12.2).

These tests mock the transport so no network access or AWS credentials are
required, and they run whether or not ``boto3`` is installed:

- A well-formed Converse response -> ``complete`` returns the expected text and
  the provider used the configured model id and an explicit ``maxTokens``.
- A transport/service error (e.g. a botocore ``ClientError``-like exception) ->
  ``complete`` raises :class:`LlmUnavailableError` (preserving Property 6).
- ``boto3`` not importable -> constructing works but using the provider raises
  :class:`LlmUnavailableError` (the ImportError path is simulated so the test
  is independent of the environment).

Requirements: 4.2, 4.5, 4.6.
"""

from __future__ import annotations

import builtins

import pytest

from backend.agent.bedrock_provider import (
    DEFAULT_MAX_TOKENS,
    BedrockNovaProvider,
    build_bedrock_provider,
)
from backend.agent.provider import LlmResult, LlmUnavailableError
from backend.config import LlmConfig


class _FakeBedrockClient:
    """Records the Converse call and returns a canned, well-formed response."""

    def __init__(self, text: str = "root cause: db connection pool exhausted") -> None:
        self._text = text
        self.calls: list[dict] = []

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": self._text}],
                }
            }
        }


class _FailingBedrockClient:
    """Simulates a botocore/ClientError-style transport failure."""

    class ClientError(Exception):
        """Stand-in for ``botocore.exceptions.ClientError``."""

    def converse(self, **kwargs: object) -> dict:
        raise self.ClientError("An error occurred (ThrottlingException)")


def _config() -> LlmConfig:
    return LlmConfig(
        model_id="us.amazon.nova-lite-v1:0",
        endpoint="https://bedrock-runtime.us-east-1.amazonaws.com",
        region="us-east-1",
    )


def test_complete_returns_text_and_uses_configured_model_and_max_tokens() -> None:
    """Well-formed response yields the text; model id + maxTokens are sent."""
    fake = _FakeBedrockClient(text="  root cause: bad deploy  ")
    provider = BedrockNovaProvider(_config(), client=fake)

    result = provider.complete("diagnose please")

    assert isinstance(result, LlmResult)
    # The provider returns the assistant text verbatim; the deterministic agent
    # is responsible for trimming/parsing.
    assert result.text == "  root cause: bad deploy  "

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["modelId"] == "us.amazon.nova-lite-v1:0"
    # maxTokens is always set explicitly (Bedrock best practice).
    assert call["inferenceConfig"]["maxTokens"] == DEFAULT_MAX_TOKENS
    # The prompt is forwarded as the single user message.
    assert call["messages"] == [
        {"role": "user", "content": [{"text": "diagnose please"}]}
    ]


def test_complete_raises_unavailable_on_transport_error() -> None:
    """Any transport/service error surfaces as LlmUnavailableError (Property 6)."""
    provider = BedrockNovaProvider(_config(), client=_FailingBedrockClient())

    with pytest.raises(LlmUnavailableError):
        provider.complete("diagnose please")


def test_complete_raises_unavailable_on_malformed_response() -> None:
    """A malformed Converse response also degrades to LlmUnavailableError."""

    class _MalformedClient:
        def converse(self, **kwargs: object) -> dict:
            return {"output": {"message": {"content": []}}}  # empty content

    provider = BedrockNovaProvider(_config(), client=_MalformedClient())

    with pytest.raises(LlmUnavailableError):
        provider.complete("diagnose please")


def test_missing_boto3_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """When boto3 cannot be imported, using the provider raises unavailable.

    Simulated by making ``import boto3`` fail, so the test is independent of
    whether boto3 is actually installed in the environment.
    """
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object):
        if name == "boto3" or name.startswith("boto3."):
            raise ImportError("No module named 'boto3'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    # No client injected, so the provider must import boto3 lazily and fail.
    provider = BedrockNovaProvider(_config())

    with pytest.raises(LlmUnavailableError):
        provider.complete("diagnose please")


def test_build_bedrock_provider_carries_config() -> None:
    """The factory constructs a provider from the given config (Req 4.6)."""
    config = _config()
    provider = build_bedrock_provider(config)

    assert provider.config.model_id == "us.amazon.nova-lite-v1:0"
    assert provider.config.region == "us-east-1"
