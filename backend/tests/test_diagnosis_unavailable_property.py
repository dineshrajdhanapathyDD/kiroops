"""Property test for LLM unavailability preserving status (Task 10.3).

Feature: incident-management, Property 6: LLM unavailability preserves incident
status.

For any existing incident, when the LLM_Provider is unavailable during a
diagnosis request, the diagnosis path returns a diagnosis-unavailable result
(surfaced here as ``DiagnosisUnavailableError``) and the incident status is left
unchanged. A fresh in-memory database is used per generated example, with the
LLM stubbed to always raise ``LlmUnavailableError``.

Validates: Requirements 4.5.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.agent.diagnosis_agent import DiagnosisAgent
from backend.agent.provider import LlmResult, LlmUnavailableError
from backend.domain.models import IncidentStatus, Severity
from backend.mcp.client import SimulatedMcpClient
from backend.repository import db
from backend.service.diagnosis_service import DiagnosisService
from backend.service.errors import DiagnosisUnavailableError
from backend.service.incident_service import IncidentService

_FIXED_NOW = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)

_non_whitespace_title = st.text(min_size=1, max_size=40).filter(
    lambda text: text.strip() != ""
)
_service = st.text(min_size=1, max_size=40)


class _AlwaysUnavailableLlm:
    """Stub LLM provider that always signals unavailability (Req 4.5)."""

    def complete(self, prompt: str) -> LlmResult:
        raise LlmUnavailableError("forced unavailable for property test")


@settings(max_examples=100)
@given(
    title=_non_whitespace_title,
    severity=st.sampled_from(list(Severity)),
    service=_service,
)
def test_llm_unavailability_preserves_incident_status(
    title: str, severity: Severity, service: str
) -> None:
    """Diagnosis is unavailable and status is unchanged when the LLM fails."""
    conn = db.in_memory()
    try:
        incidents = IncidentService(conn, now=lambda: _FIXED_NOW)
        created = incidents.create(title, severity, service)
        status_before = incidents.get(created.incident_id).incident.status
        assert status_before == IncidentStatus.OPEN

        agent = DiagnosisAgent(SimulatedMcpClient(), _AlwaysUnavailableLlm())
        diagnosis = DiagnosisService(conn, agent, now=lambda: _FIXED_NOW)

        # The diagnosis path signals unavailability (Req 4.5).
        with pytest.raises(DiagnosisUnavailableError):
            diagnosis.diagnose(created.incident_id)

        # The incident status is left unchanged.
        status_after = incidents.get(created.incident_id).incident.status
        assert status_after == status_before
        assert status_after == IncidentStatus.OPEN
    finally:
        conn.close()
