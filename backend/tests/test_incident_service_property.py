"""Property test for created-incident persisted state (Task 6.2).

Feature: incident-management, Property 1: Created incident is persisted with
initial state.

For any valid creation input (non-empty/non-whitespace title, valid Severity,
service), creating an incident then reading it back yields an incident whose
title, severity, and service equal the input, whose status is OPEN, and whose
timeline begins with a "created" event bearing a timestamp. A fresh in-memory
database is used per generated example.

Validates: Requirements 1.1, 1.4, 1.5.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.domain.models import IncidentStatus, Severity, TimelineEventType
from backend.repository import db
from backend.service.incident_service import IncidentService

_FIXED_NOW = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)

# Titles that survive validation: at least one non-whitespace character.
_non_whitespace_title = st.text(min_size=1, max_size=40).filter(
    lambda text: text.strip() != ""
)
_service = st.text(min_size=1, max_size=40)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    title=_non_whitespace_title,
    severity=st.sampled_from(list(Severity)),
    service=_service,
)
def test_created_incident_is_persisted_with_initial_state(
    title: str, severity: Severity, service: str
) -> None:
    """Create then read back; assert persisted fields, OPEN status, first event."""
    conn = db.in_memory()
    try:
        service_layer = IncidentService(conn, now=lambda: _FIXED_NOW)
        created = service_layer.create(title, severity, service)

        detail = service_layer.get(created.incident_id)

        # Persisted fields equal the input.
        assert detail.incident.title == title
        assert detail.incident.severity == severity
        assert detail.incident.service == service
        # Initial status is OPEN (Req 1.4).
        assert detail.incident.status == IncidentStatus.OPEN
        # Timeline begins with a "created" event bearing a timestamp (Req 1.5).
        assert len(detail.timeline) >= 1
        first = detail.timeline[0]
        assert first.type == TimelineEventType.CREATED
        assert first.timestamp == _FIXED_NOW
    finally:
        conn.close()
