"""LLM provider boundary and diagnosis result types (Task 10.1).

This module defines the *only* non-deterministic boundary of the diagnosis
flow as a narrow, injectable contract, plus the deterministic result types the
:class:`~backend.agent.diagnosis_agent.DiagnosisAgent` produces.

It is intentionally dependency-free: no ``boto3``/``anthropic`` import lives
here (a concrete Bedrock/Anthropic-backed provider is the optional later Task
12). Keeping the boundary abstract lets the deterministic core be unit- and
property-tested with a stub provider that returns canned output or raises
``LlmUnavailableError``.

The model identifier and endpoint are supplied through
:class:`backend.config.LlmConfig` (reused here, not redefined) so the agent
uses the configured values when calling the provider (Req 4.6).

Requirements: 4.2, 4.5, 4.6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class LlmUnavailableError(Exception):
    """Raised by an :class:`LlmProvider` when the model cannot be reached.

    Signals that the LLM boundary is unavailable or returned an error. The
    agent catches this and yields a :class:`DiagnosisUnavailable` result without
    producing a diagnosis, so the incident status is left unchanged (Req 4.5).
    """


@dataclass(frozen=True)
class LlmResult:
    """The raw text output returned by a successful ``complete`` call.

    Kept deliberately small: a single ``text`` payload the agent parses
    deterministically into a :class:`DiagnosisResult`.
    """

    text: str


@runtime_checkable
class LlmProvider(Protocol):
    """Narrow contract over the real LLM integration (Req 4.2, 4.6).

    Implementations call the configured model/endpoint. On any failure they
    raise :class:`LlmUnavailableError`. The agent depends only on this Protocol,
    so tests inject a stub (canned success or forced unavailability) and no test
    hits a live model.
    """

    def complete(self, prompt: str) -> LlmResult:
        """Complete ``prompt`` and return an :class:`LlmResult`.

        Raises :class:`LlmUnavailableError` if the provider is unavailable.
        """
        ...


@dataclass(frozen=True)
class RemediationSuggestion:
    """A single remediation step parsed from the model output (Req 5.1).

    This is the agent-level (pre-persistence) shape: it carries no ``action_id``
    or ``incident_id``. The :class:`~backend.service.diagnosis_service.DiagnosisService`
    assigns deterministic ids and the incident id when turning these into
    persisted ``RemediationAction`` domain objects.
    """

    description: str
    rationale: str


@dataclass(frozen=True)
class DiagnosisResult:
    """A successfully produced diagnosis (Req 4.2, 5.1).

    ``evidence_refs`` reference the evidence gathered from the MCP tools, and
    ``remediation_actions`` are the steps derived from the model output. This is
    the success arm of the agent's return type; the failure arm is
    :class:`DiagnosisUnavailable`.
    """

    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    remediation_actions: list[RemediationSuggestion] = field(default_factory=list)


@dataclass(frozen=True)
class DiagnosisUnavailable:
    """Sentinel result meaning the LLM was unavailable (Req 4.5).

    Returned by the agent when ``complete`` raised :class:`LlmUnavailableError`.
    No diagnosis is produced and the incident status must be left unchanged.
    """


# The agent's ``diagnose`` return type: either a diagnosis or the unavailable
# sentinel. Callers discriminate with ``isinstance(result, DiagnosisUnavailable)``.
DiagnosisOutcome = DiagnosisResult | DiagnosisUnavailable
