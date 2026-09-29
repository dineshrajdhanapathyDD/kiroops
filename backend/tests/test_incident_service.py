"""Unit tests for IncidentService validation and status edge cases (Task 6.4).

Covers create validation (whitespace-only title, non-enum severity), the
status-update transition rules (invalid/backward transition leaves status
unchanged), and not-found handling for unknown ids.

Requirements: 1.6, 1.7, 3.3, 3.4.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.domain.models import IncidentStatus, Severity, TimelineEventType
from backend.repository import db
from backend.service.errors import (
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)
from backend.service.incident_service import IncidentService

_FIXED_NOW = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)


def _service(conn) -> IncidentService:
    return IncidentService(conn, now=lambda: _FIXED_NOW)


# --- Create validation (Req 1.6, 1.7) ---------------------------------------


@pytest.mark.parametrize("title", ["", "   ", "\t", "\n", "  \t\n "])
def test_whitespace_only_title_rejected(title: str) -> None:
    """Empty or whitespace-only titles are rejected naming the title field."""
    conn = db.in_memory()
    try:
        with pytest.raises(ValidationError) as excinfo:
            _service(conn).create(title, Severity.HIGH, "payments")
        assert excinfo.value.field == "title"
        # No incident was persisted.
        assert _service(conn).list() == []
    finally:
        conn.close()


def test_non_enum_severity_rejected() -> None:
    """A severity that is not a Severity member is rejected naming severity."""
    conn = db.in_memory()
    try:
        with pytest.raises(ValidationError) as excinfo:
            _service(conn).create("db outage", "SEVERE", "payments")  # type: ignore[arg-type]
        assert excinfo.value.field == "severity"
        assert _service(conn).list() == []
    finally:
        conn.close()


def test_create_valid_incident_starts_open_with_created_event() -> None:
    """A valid create persists an OPEN incident with a leading created event."""
    conn = db.in_memory()
    try:
        svc = _service(conn)
        incident = svc.create("db outage", Severity.CRITICAL, "payments")
        assert incident.status == IncidentStatus.OPEN

        detail = svc.get(incident.incident_id)
        assert detail.timeline[0].type == TimelineEventType.CREATED
        assert detail.timeline[0].timestamp == _FIXED_NOW
    finally:
        conn.close()


# --- Status update edge cases (Req 3.3, 3.4) --------------------------------


def test_valid_transition_updates_status_and_appends_event() -> None:
    """OPEN -> INVESTIGATING persists and records a status changed event."""
    conn = db.in_memory()
    try:
        svc = _service(conn)
        incident = svc.create("db outage", Severity.HIGH, "payments")

        updated = svc.update_status(incident.incident_id, IncidentStatus.INVESTIGATING)
        assert updated.status == IncidentStatus.INVESTIGATING

        detail = svc.get(incident.incident_id)
        assert detail.incident.status == IncidentStatus.INVESTIGATING
        last = detail.timeline[-1]
        assert last.type == TimelineEventType.STATUS_CHANGED
        assert last.details == {"from": "OPEN", "to": "INVESTIGATING"}
    finally:
        conn.close()


@pytest.mark.parametrize(
    "target",
    [
        IncidentStatus.OPEN,  # same-state
        IncidentStatus.RESOLVED,  # skip-ahead OPEN -> RESOLVED
    ],
)
def test_invalid_transition_from_open_preserves_status(
    target: IncidentStatus,
) -> None:
    """An invalid transition raises and leaves the stored status unchanged."""
    conn = db.in_memory()
    try:
        svc = _service(conn)
        incident = svc.create("db outage", Severity.HIGH, "payments")

        with pytest.raises(InvalidTransitionError):
            svc.update_status(incident.incident_id, target)

        detail = svc.get(incident.incident_id)
        assert detail.incident.status == IncidentStatus.OPEN
        # No status changed event was appended (only the created event remains).
        assert all(
            event.type != TimelineEventType.STATUS_CHANGED
            for event in detail.timeline
        )
    finally:
        conn.close()


def test_backward_transition_preserves_status() -> None:
    """A backward transition (INVESTIGATING -> OPEN) is rejected, status kept."""
    conn = db.in_memory()
    try:
        svc = _service(conn)
        incident = svc.create("db outage", Severity.HIGH, "payments")
        svc.update_status(incident.incident_id, IncidentStatus.INVESTIGATING)

        with pytest.raises(InvalidTransitionError):
            svc.update_status(incident.incident_id, IncidentStatus.OPEN)

        detail = svc.get(incident.incident_id)
        assert detail.incident.status == IncidentStatus.INVESTIGATING
    finally:
        conn.close()


def test_update_status_unknown_id_raises_not_found() -> None:
    """Updating an unknown incident id raises NotFoundError."""
    conn = db.in_memory()
    try:
        with pytest.raises(NotFoundError):
            _service(conn).update_status("INC-9999", IncidentStatus.INVESTIGATING)
    finally:
        conn.close()


def test_get_unknown_id_raises_not_found() -> None:
    """Reading an unknown incident id raises NotFoundError (Req 2.3)."""
    conn = db.in_memory()
    try:
        with pytest.raises(NotFoundError):
            _service(conn).get("INC-9999")
    finally:
        conn.close()
