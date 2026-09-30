"""Property test for DynamoDB incident id generation (Phase 1).

Feature: incident-management, Property 2: Incident IDs are well-formed, unique,
and monotonic.

Re-verifies Property 2 against the DynamoDB backend: for any sequence of
creations, every assigned id matches ``^INC-\\d{4,}$``, all ids are pairwise
distinct, and the numeric portions are strictly increasing in creation order.
The atomic counter (``UpdateItem ADD ... UPDATED_NEW``) is what guarantees this.
A fresh moto table is stood up per generated example.

Validates: Requirements 1.2, 1.3, 7.1, 7.2.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.domain.models import Severity
from backend.repository.dynamo_incident_repository import DynamoIncidentRepository
from backend.tests.dynamo_support import fresh_table

_ID_PATTERN = re.compile(r"^INC-\d{4,}$")

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


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(creations=st.lists(_CREATION, min_size=1, max_size=25))
def test_ids_are_well_formed_unique_and_monotonic(
    creations: list[tuple[str, Severity, str]],
) -> None:
    """Generate N creations against a fresh table and check the id invariants."""
    with fresh_table() as table:
        repo = DynamoIncidentRepository(table)
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
