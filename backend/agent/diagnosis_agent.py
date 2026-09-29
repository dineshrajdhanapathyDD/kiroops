"""DiagnosisAgent: deterministic orchestration over MCP + the LLM (Task 10.2).

The agent gathers evidence from all four MCP tools, assembles a deterministic
prompt, calls the injected :class:`~backend.agent.provider.LlmProvider`, and
parses the result into a :class:`~backend.agent.provider.DiagnosisResult`. The
only non-deterministic step is ``llm.complete``; ``_gather_evidence``,
``_build_prompt`` and ``_parse`` are pure and unit-testable in isolation.

On :class:`~backend.agent.provider.LlmUnavailableError` the agent returns a
:class:`~backend.agent.provider.DiagnosisUnavailable` sentinel WITHOUT producing
a diagnosis, so a caller can leave the incident status unchanged (Req 4.5).

Requirements: 4.1, 4.2, 4.6, 5.1.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.agent.provider import (
    DiagnosisOutcome,
    DiagnosisResult,
    DiagnosisUnavailable,
    LlmProvider,
    LlmResult,
    LlmUnavailableError,
    RemediationSuggestion,
)
from backend.domain.models import Incident
from backend.mcp.client import McpClient


@dataclass(frozen=True)
class Evidence:
    """The bundle of evidence gathered from the four MCP tools (Req 4.1).

    Held as a structured, deterministic value so ``_build_prompt`` and the
    ``evidence_refs`` derivation are pure functions of it.
    """

    service: str
    logs: dict
    metrics: dict
    history: dict
    runbook: dict


class DiagnosisAgent:
    """Deterministic evidence-gathering orchestration around one LLM call."""

    def __init__(self, mcp_client: McpClient, llm: LlmProvider) -> None:
        self._mcp = mcp_client
        self._llm = llm

    def diagnose(self, incident: Incident) -> DiagnosisOutcome:
        """Produce a diagnosis for ``incident`` or signal unavailability.

        Gathers evidence (Req 4.1), builds a deterministic prompt, calls the LLM
        (Req 4.2), and parses the output into a diagnosis with derived
        remediation actions (Req 5.1). If the LLM is unavailable, returns
        :class:`DiagnosisUnavailable` without producing a diagnosis (Req 4.5).
        """
        evidence = self._gather_evidence(incident.service, incident.title)
        prompt = self._build_prompt(incident, evidence)
        try:
            raw = self._llm.complete(prompt)
        except LlmUnavailableError:
            return DiagnosisUnavailable()
        return self._parse(raw, evidence)

    def _gather_evidence(self, service: str, query: str) -> Evidence:
        """Invoke all four MCP tools for the incident service (Req 4.1).

        Pure with respect to the (stubbed) MCP client: given the same client
        responses it always returns the same :class:`Evidence`.
        """
        logs = self._mcp.get_recent_logs(service)
        metrics = self._mcp.get_service_metrics(service)
        history = self._mcp.get_incident_history(service)
        runbook = self._mcp.search_runbook(service, query)
        return Evidence(
            service=service,
            logs=dict(logs),
            metrics=dict(metrics),
            history=dict(history),
            runbook=dict(runbook),
        )

    def _build_prompt(self, incident: Incident, evidence: Evidence) -> str:
        """Assemble a deterministic prompt from the incident and evidence.

        The layout is fixed and ordered so the same inputs always produce the
        same prompt string, keeping the agent testable. The evidence reference
        labels embedded here match those returned in the parsed
        ``evidence_refs`` (see :meth:`_evidence_refs`).
        """
        lines = [
            "You are KiroOps, an incident diagnosis assistant.",
            "Diagnose the incident using ONLY the gathered evidence below.",
            "",
            f"Incident: {incident.incident_id}",
            f"Title: {incident.title}",
            f"Severity: {incident.severity.value}",
            f"Service: {incident.service}",
            f"Status: {incident.status.value}",
            "",
            "Evidence:",
        ]
        for ref in self._evidence_refs(evidence):
            lines.append(f"- {ref}")
        lines.extend(
            [
                "",
                f"recent_logs: {evidence.logs}",
                f"service_metrics: {evidence.metrics}",
                f"incident_history: {evidence.history}",
                f"runbook_search: {evidence.runbook}",
            ]
        )
        return "\n".join(lines)

    def _evidence_refs(self, evidence: Evidence) -> list[str]:
        """Derive stable references to the gathered evidence (Req 4.2).

        Deterministic, order-stable labels the diagnosis cites. Counts are
        derived from the evidence so the references summarize what was gathered.
        """
        log_count = len(evidence.logs.get("entries", []))
        history_count = len(evidence.history.get("incidents", []))
        runbook_count = len(evidence.runbook.get("matches", []))
        metric_names = sorted((evidence.metrics.get("metrics") or {}).keys())
        return [
            f"logs:{evidence.service}:{log_count} entries",
            f"metrics:{evidence.service}:{','.join(metric_names)}",
            f"history:{evidence.service}:{history_count} incidents",
            f"runbook:{evidence.service}:{runbook_count} matches",
        ]

    def _parse(self, raw: LlmResult, evidence: Evidence) -> DiagnosisResult:
        """Parse model output into a diagnosis with remediation actions.

        Deterministic: the summary is the model text (trimmed), the
        ``evidence_refs`` are re-derived from the gathered evidence, and
        remediation suggestions are derived from the runbook matches in the
        evidence (falling back to a generic step when none were found), so the
        actions are grounded in what was gathered (Req 5.1).
        """
        summary = raw.text.strip()
        evidence_refs = self._evidence_refs(evidence)
        remediation_actions = self._derive_actions(evidence)
        return DiagnosisResult(
            summary=summary,
            evidence_refs=evidence_refs,
            remediation_actions=remediation_actions,
        )

    def _derive_actions(self, evidence: Evidence) -> list[RemediationSuggestion]:
        """Derive remediation suggestions from the runbook evidence (Req 5.1).

        Order is preserved from the (already score-sorted) runbook matches so the
        derivation is deterministic.
        """
        matches = evidence.runbook.get("matches", [])
        suggestions: list[RemediationSuggestion] = []
        for match in matches:
            title = match.get("title", "Remediation step")
            excerpt = match.get("excerpt", "")
            suggestions.append(
                RemediationSuggestion(description=title, rationale=excerpt)
            )
        if not suggestions:
            suggestions.append(
                RemediationSuggestion(
                    description="Investigate the affected service",
                    rationale=(
                        "No runbook match was found; review recent logs and "
                        "metrics for the affected service."
                    ),
                )
            )
        return suggestions
