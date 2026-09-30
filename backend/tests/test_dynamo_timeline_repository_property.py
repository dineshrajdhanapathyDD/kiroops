"""Property tests for the DynamoDB append-only timeline (Phase 1).

Feature: incident-management, Property 4: Timeline is append-only.
Feature: incident-management, Property 5: Timeline is returned in chronological
order.

Re-verifies the two storage-level timeline properties against the DynamoDB
backend. Each example first creates an incident, then appends events to it. A
fresh moto table is stood up per generated example.

On this backend, ``seq`` is assigned by a per-incident atomic counter in append
order and is the sort key, so ``list`` returns events in ascending ``seq`` order
== append order == chronological order (Property 5). ``append`` never
overwrites a prior event (Property 4).

Validates: Requirements 2.2, 6.2, 6.3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.domain.models import Severity, TimelineEvent, TimelineEventType
from backend.repository.dynamo_incident_repository import DynamoIncidentRepository
from backend.repository.dynamo_timeline_repository import DynamoTimelineRepository
from backend.tests.dynamo_support import fresh_table

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


def _new_incident_with_timeline(table) -> tuple[str, DynamoTimelineRepository]:
    """Create an incident and return its id plus a timeline repository."""
    incident = DynamoIncidentRepository(table).create(
        "t", Severity.LOW, "svc", _BASE
    )
    return incident.incident_id, DynamoTimelineRepository(table)


def _append(
    timeline: DynamoTimelineRepository,
    incident_id: str,
    event: tuple[TimelineEventType, int, dict],
) -> None:
    event_type, offset, details = event
    timeline.append(
        incident_id, event_type, _BASE + timedelta(seconds=offset), details
    )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    existing=st.lists(_EVENT, max_size=10),
    new_event=_EVENT,
)
def test_append_is_append_only(
    existing: list[tuple[TimelineEventType, int, dict]],
    new_event: tuple[TimelineEventType, int, dict],
) -> None:
    """Appending never mutates or removes prior events (Property 4)."""
    with fresh_table() as table:
        incident_id, timeline = _new_incident_with_timeline(table)
        for event in existing:
            _append(timeline, incident_id, event)

        before: list[TimelineEvent] = timeline.list(incident_id)
        _append(timeline, incident_id, new_event)
        after: list[TimelineEvent] = timeline.list(incident_id)

        # Timeline grew by exactly one event.
        assert len(after) == len(before) + 1

        # Every prior event is still present and unchanged (keyed by seq).
        before_by_seq = {e.seq: e for e in before}
        for event in after:
            if event.seq in before_by_seq:
                assert event == before_by_seq[event.seq]

        # The set of prior seqs is preserved (none dropped).
        assert before_by_seq.keys() <= {e.seq for e in after}


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(events=st.lists(_EVENT, min_size=1, max_size=15))
def test_list_is_chronological(
    events: list[tuple[TimelineEventType, int, dict]],
) -> None:
    """list() returns events earliest -> latest by append order (Property 5)."""
    with fresh_table() as table:
        incident_id, timeline = _new_incident_with_timeline(table)
        for event in events:
            _append(timeline, incident_id, event)

        listed = timeline.list(incident_id)

        # One stored event per append, and seq is strictly increasing in the
        # returned order (== append order == chronological on this backend).
        assert len(listed) == len(events)
        seqs = [e.seq for e in listed]
        assert seqs == sorted(seqs)
        for earlier, later in zip(seqs, seqs[1:]):
            assert later > earlier
