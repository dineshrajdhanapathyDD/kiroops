"""Property tests for the append-only timeline (Tasks 4.4, 4.5).

Feature: incident-management, Property 4: Timeline is append-only.
Feature: incident-management, Property 5: Timeline is returned in chronological
order.

Foreign keys are ON, so each example first creates an incident before appending
timeline events to it. A fresh in-memory database is used per generated example.

Validates: Requirements 2.2, 6.2, 6.3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.domain.models import Severity, TimelineEvent, TimelineEventType
from backend.repository import db
from backend.repository.incident_repository import IncidentRepository
from backend.repository.timeline_repository import TimelineRepository

_BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)

# A single event to append: (type, timestamp offset in seconds, details).
_EVENT = st.tuples(
    st.sampled_from(list(TimelineEventType)),
    st.integers(min_value=0, max_value=100_000),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.text(max_size=16),
        max_size=4,
    ),
)


def _new_incident_with_timeline(conn) -> tuple[str, TimelineRepository]:
    """Create an incident and return its id plus a timeline repository."""
    incident = IncidentRepository(conn).create(
        "t", Severity.LOW, "svc", _BASE
    )
    return incident.incident_id, TimelineRepository(conn)


def _append(
    timeline: TimelineRepository,
    incident_id: str,
    event: tuple[TimelineEventType, int, dict],
) -> None:
    event_type, offset, details = event
    timeline.append(
        incident_id, event_type, _BASE + timedelta(seconds=offset), details
    )


@settings(max_examples=100)
@given(
    existing=st.lists(_EVENT, max_size=10),
    new_event=_EVENT,
)
def test_append_is_append_only(
    existing: list[tuple[TimelineEventType, int, dict]],
    new_event: tuple[TimelineEventType, int, dict],
) -> None:
    """Appending never mutates or removes prior events (Property 4)."""
    conn = db.in_memory()
    try:
        incident_id, timeline = _new_incident_with_timeline(conn)
        for event in existing:
            _append(timeline, incident_id, event)

        before: list[TimelineEvent] = timeline.list(incident_id)
        _append(timeline, incident_id, new_event)
        after: list[TimelineEvent] = timeline.list(incident_id)

        # Timeline grew by exactly one event.
        assert len(after) == len(before) + 1

        # Every prior event is still present and unchanged. Compare against the
        # same ordering (by (timestamp, seq)) that both snapshots use.
        before_by_seq = {e.seq: e for e in before}
        for event in after:
            if event.seq in before_by_seq:
                assert event == before_by_seq[event.seq]

        # The set of prior seqs is preserved (none dropped).
        assert before_by_seq.keys() <= {e.seq for e in after}
    finally:
        conn.close()


@settings(max_examples=100)
@given(events=st.lists(_EVENT, min_size=1, max_size=15))
def test_list_is_chronological(
    events: list[tuple[TimelineEventType, int, dict]],
) -> None:
    """list() returns events ordered earliest -> latest by timestamp (Property 5)."""
    conn = db.in_memory()
    try:
        incident_id, timeline = _new_incident_with_timeline(conn)
        for event in events:
            _append(timeline, incident_id, event)

        listed = timeline.list(incident_id)

        # Non-decreasing by timestamp, and seq breaks ties in append order.
        for earlier, later in zip(listed, listed[1:]):
            assert (earlier.timestamp, earlier.seq) <= (
                later.timestamp,
                later.seq,
            )
    finally:
        conn.close()
