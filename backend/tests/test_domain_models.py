"""Unit tests for domain enums and dataclasses (Task 2.4).

Asserts enum string values match design.md exactly and dataclass construction
works with the fields defined in the design.

Requirements: 1.4, 6.1.
"""

from __future__ import annotations

from datetime import datetime

from backend.domain.models import (
    Diagnosis,
    Incident,
    IncidentStatus,
    RemediationAction,
    Severity,
    TimelineEvent,
    TimelineEventType,
)


def test_severity_values_match_design() -> None:
    assert Severity.LOW.value == "LOW"
    assert Severity.MEDIUM.value == "MEDIUM"
    assert Severity.HIGH.value == "HIGH"
    assert Severity.CRITICAL.value == "CRITICAL"
    assert [s.value for s in Severity] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_incident_status_values_match_design() -> None:
    assert IncidentStatus.OPEN.value == "OPEN"
    assert IncidentStatus.INVESTIGATING.value == "INVESTIGATING"
    assert IncidentStatus.RESOLVED.value == "RESOLVED"
    assert [s.value for s in IncidentStatus] == [
        "OPEN",
        "INVESTIGATING",
        "RESOLVED",
    ]


def test_timeline_event_type_values_match_design() -> None:
    # The exact human-readable strings from design.md, including spaces.
    assert TimelineEventType.CREATED.value == "created"
    assert TimelineEventType.STATUS_CHANGED.value == "status changed"
    assert TimelineEventType.DIAGNOSIS_REQUESTED.value == "diagnosis requested"
    assert TimelineEventType.ACTIONS_SUGGESTED.value == "actions suggested"


def test_str_enum_members_compare_equal_to_their_string() -> None:
    # (str, Enum) members are usable directly as their string value.
    assert Severity.HIGH == "HIGH"
    assert IncidentStatus.OPEN == "OPEN"
    assert TimelineEventType.STATUS_CHANGED == "status changed"


def test_incident_construction() -> None:
    created = datetime(2024, 1, 1, 12, 0, 0)
    incident = Incident(
        incident_id="INC-0001",
        title="Checkout latency spike",
        severity=Severity.HIGH,
        service="checkout",
        status=IncidentStatus.OPEN,
        created_at=created,
    )
    assert incident.incident_id == "INC-0001"
    assert incident.title == "Checkout latency spike"
    assert incident.severity is Severity.HIGH
    assert incident.service == "checkout"
    assert incident.status is IncidentStatus.OPEN
    assert incident.created_at == created


def test_timeline_event_construction() -> None:
    ts = datetime(2024, 1, 1, 12, 0, 0)
    event = TimelineEvent(
        incident_id="INC-0001",
        seq=1,
        type=TimelineEventType.CREATED,
        timestamp=ts,
        details={"note": "opened"},
    )
    assert event.incident_id == "INC-0001"
    assert event.seq == 1
    assert event.type is TimelineEventType.CREATED
    assert event.timestamp == ts
    assert event.details == {"note": "opened"}


def test_diagnosis_construction() -> None:
    created = datetime(2024, 1, 1, 12, 5, 0)
    diagnosis = Diagnosis(
        incident_id="INC-0001",
        summary="Database connection pool exhausted",
        evidence_refs=["logs:checkout", "metrics:checkout"],
        created_at=created,
    )
    assert diagnosis.incident_id == "INC-0001"
    assert diagnosis.summary == "Database connection pool exhausted"
    assert diagnosis.evidence_refs == ["logs:checkout", "metrics:checkout"]
    assert diagnosis.created_at == created


def test_remediation_action_construction() -> None:
    action = RemediationAction(
        action_id="ACT-0001",
        incident_id="INC-0001",
        description="Increase connection pool size",
        rationale="Pool exhaustion correlated with error spike",
    )
    assert action.action_id == "ACT-0001"
    assert action.incident_id == "INC-0001"
    assert action.description == "Increase connection pool size"
    assert action.rationale == "Pool exhaustion correlated with error spike"
