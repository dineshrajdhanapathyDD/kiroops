"""Property test for incident id generation (Task 4.2).

Feature: incident-management, Property 2: Incident IDs are well-formed, unique,
and monotonic.

For any sequence of creations, every assigned id matches ``^INC-\\d{4,}$``, all
ids are pairwise distinct, and the numeric portions are strictly increasing in
creation order. A fresh in-memory database is used per generated example.

Validates: Requirements 1.2, 1.3, 7.1, 7.2.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.domain.models import Severity
from backend.repository import db
from backend.repository.incident_repository import IncidentRepository

_ID_PATTERN = re.compile(r"^INC-\d{4,}$")

# A single creation input: (title, severity, service). Titles/services are kept
# non-empty but drawn from a small ASCII alphabet with a short max length: the id
# invariant under test does not depend on their content, so cheap values give
# full coverage while keeping per-example input generation inexpensive.
_SHORT_TEXT = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),  # a-z
    min_size=1,
    max_size=5,
)
_CREATION = st.tuples(
    _SHORT_TEXT,
    st.sampled_from(list(Severity)),
    _SHORT_TEXT,
)


# ``too_slow`` is suppressed because input-generation timing is environment
# sensitive on newer Hypothesis builds; the property itself is cheap and the
# generators above are intentionally minimal.
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(creations=st.lists(_CREATION, min_size=1, max_size=25))
def test_ids_are_well_formed_unique_and_monotonic(
    creations: list[tuple[str, Severity, str]],
) -> None:
    """Generate N creations against a fresh DB and check the id invariants."""
    conn = db.in_memory()
    try:
        repo = IncidentRepository(conn)
        created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ids: list[str] = []
        for title, severity, service in creations:
            incident = repo.create(title, severity, service, created_at)
            ids.append(incident.incident_id)

        # Well-formed: every id is non-empty and matches INC-\d{4,}.
        for incident_id in ids:
            assert incident_id, "incident_id must be non-empty"
            assert _ID_PATTERN.match(incident_id), incident_id

        # Unique: all ids pairwise distinct.
        assert len(set(ids)) == len(ids)

        # Monotonic: numeric portions strictly increasing in creation order.
        numeric = [int(i.removeprefix("INC-")) for i in ids]
        for earlier, later in zip(numeric, numeric[1:]):
            assert later > earlier
    finally:
        conn.close()
