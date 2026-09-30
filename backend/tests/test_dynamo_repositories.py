"""Round-trip unit tests for the DynamoDB repositories (Phase 1).

Covers incident create/get/list/update_status (including GSI-backed list
ordering), diagnosis save/get, and remediation save_all/list against a fresh
moto table. These mirror the SQLite repository unit tests so both backends have
equivalent example coverage.

Requirements: 1.1, 2.1, 2.2, 3.1, 4.4, 5.3.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.domain.models import (
    Diagnosis,
    IncidentStatus,
    RemediationAction,
    Severity,
)
from backend.repository.dynamo_diagnosis_repository import DynamoDiagnosisRepository
from backend.repository.dynamo_incident_repository import DynamoIncidentRepository
from backend.repository.dynamo_remediation_repository import (
    DynamoRemediationRepository,
)
from backend.tests.dynamo_support import fresh_table

_CREATED_AT = datetime(2024, 3, 4, 5, 6, 7, tzinfo=timezone.utc)


def test_incident_create_get_round_trip() -> None:
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
        created = repo.create("db outage", Severity.HIGH, "payments", _CREATED_AT)

        assert created.incident_id == "INC-0001"
        assert created.status is IncidentStatus.OPEN

        loaded = repo.get(created.incident_id)
        assert loaded == created
        assert loaded is not None
        assert loaded.severity is Severity.HIGH
        assert loaded.created_at == _CREATED_AT


def test_incident_get_missing_returns_none() -> None:
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
        assert repo.get("INC-9999") is None


def test_incident_list_orders_by_id_ascending_via_gsi() -> None:
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
        first = repo.create("a", Severity.LOW, "svc", _CREATED_AT)
        second = repo.create("b", Severity.MEDIUM, "svc", _CREATED_AT)
        third = repo.create("c", Severity.CRITICAL, "svc", _CREATED_AT)

        listed = repo.list()
        assert [i.incident_id for i in listed] == [
            first.incident_id,
            second.incident_id,
            third.incident_id,
        ]
        # The index carries only incident META items (one entry per incident).
        assert len(listed) == 3


def test_incident_list_empty_when_none_created() -> None:
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
        assert repo.list() == []


def test_incident_update_status_persists_new_value() -> None:
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
        created = repo.create("db outage", Severity.HIGH, "payments", _CREATED_AT)

        repo.update_status(created.incident_id, IncidentStatus.INVESTIGATING)
        reloaded = repo.get(created.incident_id)
        assert reloaded is not None
        assert reloaded.status is IncidentStatus.INVESTIGATING

        repo.update_status(created.incident_id, IncidentStatus.RESOLVED)
        reloaded = repo.get(created.incident_id)
        assert reloaded is not None
        assert reloaded.status is IncidentStatus.RESOLVED


def test_diagnosis_save_get_round_trip() -> None:
    with fresh_table() as table:
        incident_id = DynamoIncidentRepository(table).create(
            "db outage", Severity.HIGH, "payments", _CREATED_AT
        ).incident_id
        repo = DynamoDiagnosisRepository(table)
        diagnosis = Diagnosis(
            incident_id=incident_id,
            summary="Connection pool exhausted under load.",
            evidence_refs=["logs:payments", "metrics:payments", "runbook:RB-12"],
            created_at=_CREATED_AT,
        )
        repo.save(diagnosis)

        loaded = repo.get(incident_id)
        assert loaded == diagnosis
        assert loaded is not None
        assert loaded.evidence_refs == diagnosis.evidence_refs
        assert loaded.created_at == _CREATED_AT


def test_diagnosis_get_missing_returns_none() -> None:
    with fresh_table() as table:
        DynamoIncidentRepository(table).create(
            "db outage", Severity.HIGH, "payments", _CREATED_AT
        )
        repo = DynamoDiagnosisRepository(table)
        assert repo.get("INC-0001") is None


def test_remediation_save_all_and_list() -> None:
    with fresh_table() as table:
        incident_id = DynamoIncidentRepository(table).create(
            "db outage", Severity.HIGH, "payments", _CREATED_AT
        ).incident_id
        repo = DynamoRemediationRepository(table)
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


def test_remediation_list_empty_when_none_saved() -> None:
    with fresh_table() as table:
        incident_id = DynamoIncidentRepository(table).create(
            "db outage", Severity.HIGH, "payments", _CREATED_AT
        ).incident_id
        repo = DynamoRemediationRepository(table)
        assert repo.list(incident_id) == []
