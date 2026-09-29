"""Unit tests for DiagnosisAgent orchestration (Task 10.4).

Exercise the deterministic orchestration with a stub ``McpClient`` and a stub
``LlmProvider`` returning canned output. Assert all four MCP tools are invoked,
the gathered evidence is passed into the prompt, the diagnosis is parsed,
remediation actions are derived, and the configured model/endpoint reaches the
provider (via ``LlmConfig``). No live model or MCP server is contacted.

Requirements: 4.1, 4.2, 4.6, 5.1.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.agent.diagnosis_agent import DiagnosisAgent
from backend.agent.provider import (
    DiagnosisResult,
    LlmResult,
    LlmUnavailableError,
)
from backend.config import LlmConfig
from backend.domain.models import Incident, IncidentStatus, Severity


class StubMcpClient:
    """Records tool calls and returns fixed, recognizable evidence shapes."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def get_recent_logs(self, service: str, limit: int = 50) -> dict:
        self.calls.append(("get_recent_logs", (service, limit)))
        return {
            "service": service,
            "entries": [
                {"timestamp": "2024-01-01T00:00:00+00:00", "level": "ERROR", "message": "boom"},
                {"timestamp": "2024-01-01T00:00:05+00:00", "level": "INFO", "message": "ok"},
            ],
        }

    def get_service_metrics(self, service: str, window_minutes: int = 15) -> dict:
        self.calls.append(("get_service_metrics", (service, window_minutes)))
        return {
            "service": service,
            "metrics": {"error_rate": 0.5, "p95_latency_ms": 900.0, "cpu_pct": 80.0, "memory_pct": 70.0},
        }

    def get_incident_history(self, service: str, limit: int = 10) -> dict:
        self.calls.append(("get_incident_history", (service, limit)))
        return {
            "service": service,
            "incidents": [
                {"incident_id": "INC-0009", "title": "old", "severity": "HIGH", "resolved_at": "2023-12-01T00:00:00+00:00"}
            ],
        }

    def search_runbook(self, service: str, query: str) -> dict:
        self.calls.append(("search_runbook", (service, query)))
        return {
            "matches": [
                {"runbook_id": "RB-001", "title": "Mitigating high error rate", "excerpt": "Roll back a bad deploy.", "score": 0.9},
                {"runbook_id": "RB-002", "title": "Scaling under CPU pressure", "excerpt": "Scale horizontally.", "score": 0.7},
            ]
        }


class RecordingLlmProvider:
    """Stub provider that records the prompt and returns canned text.

    Built from an ``LlmConfig`` so the test can assert the agent/provider was
    given the configured model id and endpoint (Req 4.6).
    """

    def __init__(self, config: LlmConfig, text: str = "root cause: db pool exhausted") -> None:
        self.config = config
        self._text = text
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> LlmResult:
        self.prompts.append(prompt)
        return LlmResult(text=self._text)


class UnavailableLlmProvider:
    """Stub provider that always signals the LLM is unavailable."""

    def complete(self, prompt: str) -> LlmResult:
        raise LlmUnavailableError("stub unavailable")


def _incident(service: str = "payments") -> Incident:
    return Incident(
        incident_id="INC-0001",
        title="checkout failing",
        severity=Severity.HIGH,
        service=service,
        status=IncidentStatus.OPEN,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_diagnose_invokes_all_four_mcp_tools() -> None:
    """All four evidence tools are called for the incident service (Req 4.1)."""
    mcp = StubMcpClient()
    llm = RecordingLlmProvider(LlmConfig("m", "e"))
    agent = DiagnosisAgent(mcp, llm)

    agent.diagnose(_incident("payments"))

    called = {name for name, _ in mcp.calls}
    assert called == {
        "get_recent_logs",
        "get_service_metrics",
        "get_incident_history",
        "search_runbook",
    }
    # Each tool was invoked for the incident's service.
    for _name, args in mcp.calls:
        assert args[0] == "payments"


def test_diagnose_passes_evidence_into_prompt() -> None:
    """The prompt embeds the gathered evidence (Req 4.2)."""
    mcp = StubMcpClient()
    llm = RecordingLlmProvider(LlmConfig("m", "e"))
    agent = DiagnosisAgent(mcp, llm)

    agent.diagnose(_incident("payments"))

    assert len(llm.prompts) == 1
    prompt = llm.prompts[0]
    # Evidence content is present in the prompt.
    assert "recent_logs" in prompt
    assert "service_metrics" in prompt
    assert "incident_history" in prompt
    assert "runbook_search" in prompt
    assert "error_rate" in prompt
    assert "payments" in prompt


def test_diagnose_parses_diagnosis_and_derives_actions() -> None:
    """Model output is parsed to a summary; actions derive from runbook (Req 5.1)."""
    mcp = StubMcpClient()
    llm = RecordingLlmProvider(LlmConfig("m", "e"), text="  root cause: db pool exhausted  ")
    agent = DiagnosisAgent(mcp, llm)

    result = agent.diagnose(_incident("payments"))

    assert isinstance(result, DiagnosisResult)
    assert result.summary == "root cause: db pool exhausted"  # trimmed
    # Evidence refs reference all four gathered sources.
    assert any(ref.startswith("logs:") for ref in result.evidence_refs)
    assert any(ref.startswith("metrics:") for ref in result.evidence_refs)
    assert any(ref.startswith("history:") for ref in result.evidence_refs)
    assert any(ref.startswith("runbook:") for ref in result.evidence_refs)
    # Two runbook matches -> two derived remediation actions, order preserved.
    assert [a.description for a in result.remediation_actions] == [
        "Mitigating high error rate",
        "Scaling under CPU pressure",
    ]
    assert result.remediation_actions[0].rationale == "Roll back a bad deploy."


def test_diagnose_uses_configured_model_and_endpoint() -> None:
    """The provider carries the configured model id and endpoint (Req 4.6)."""
    mcp = StubMcpClient()
    config = LlmConfig(model_id="anthropic.claude-x", endpoint="https://example.test")
    llm = RecordingLlmProvider(config)
    agent = DiagnosisAgent(mcp, llm)

    agent.diagnose(_incident())

    assert llm.config.model_id == "anthropic.claude-x"
    assert llm.config.endpoint == "https://example.test"


def test_diagnose_returns_unavailable_without_producing_diagnosis() -> None:
    """On LlmUnavailableError the agent yields DiagnosisUnavailable (Req 4.5)."""
    from backend.agent.provider import DiagnosisUnavailable

    mcp = StubMcpClient()
    agent = DiagnosisAgent(mcp, UnavailableLlmProvider())

    result = agent.diagnose(_incident())

    assert isinstance(result, DiagnosisUnavailable)
    # Evidence was still gathered (tools invoked) before the failed LLM call.
    assert {name for name, _ in mcp.calls} == {
        "get_recent_logs",
        "get_service_metrics",
        "get_incident_history",
        "search_runbook",
    }
