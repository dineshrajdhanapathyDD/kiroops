"""Unit tests for the diagnosis and remediation repositories (Task 4.7).

Foreign keys are ON, so an incident is created before diagnosis/remediation
rows reference it. Covers save/get round-trip for diagnosis and save_all/list
for remediation actions.

Requirements: 4.4, 5.3.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.domain.models import (
    Diagnosis,
    RemediationAction,
    Severity,
)
from backend.repository import db
from backend.repository.diagnosis_repository import DiagnosisRepository
from backend.repository.incident_repository import IncidentRepository
from backend.repository.remediation_repository import RemediationRepository

_CREATED_AT = datetime(2024, 3, 4, 5, 6, 7, tzinfo=timezone.utc)


def _new_incident(conn) -> str:
    incident = IncidentRepository(conn).create(
        "db outage", Severity.HIGH, "payments", _CREATED_AT
    )
    return incident.incident_id


def test_diagnosis_save_get_round_trip() -> None:
    conn = db.in_memory()
    try:
        incident_id = _new_incident(conn)
        repo = DiagnosisRepository(conn)
        diagnosis = Diagnosis(
            incident_id=incident_id,
            summary="Connection pool exhausted under load.",
            evidence_refs=["logs:payments", "metrics:payments", "runbook:RB-12"],
            created_at=_CREATED_AT,
        )
        repo.save(diagnosis)

        loaded = repo.get(incident_id)
        assert loaded == diagnosis
        # evidence_refs round-trips as a list, created_at as a datetime.
        assert loaded is not None
        assert loaded.evidence_refs == diagnosis.evidence_refs
        assert loaded.created_at == _CREATED_AT
    finally:
        conn.close()


def test_diagnosis_get_missing_returns_none() -> None:
    conn = db.in_memory()
    try:
        _new_incident(conn)  # exists, but no diagnosis saved
        repo = DiagnosisRepository(conn)
        assert repo.get("INC-0001") is None
    finally:
        conn.close()


def test_remediation_save_all_and_list() -> None:
    conn = db.in_memory()
    try:
        incident_id = _new_incident(conn)
        repo = RemediationRepository(conn)
        actions = [
            RemediationAction(
                action_id="ACT-0001",
                incident_id=incident_id,
                description="Increase connection pool size.",
                rationale="Pool exhaustion observed in metrics.",
            ),
            RemediationAction(
                action_id="ACT-0002",
                incident_id=incident_id,
                description="Add retry with backoff.",
                rationale="Transient failures in logs.",
            ),
        ]
        repo.save_all(actions)

        listed = repo.list(incident_id)
        assert listed == actions
    finally:
        conn.close()


def test_remediation_list_empty_when_none_saved() -> None:
    conn = db.in_memory()
    try:
        incident_id = _new_incident(conn)
        repo = RemediationRepository(conn)
        assert repo.list(incident_id) == []
    finally:
        conn.close()
