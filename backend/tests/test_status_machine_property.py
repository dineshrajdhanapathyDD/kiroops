"""Property test for the pure status state machine (Task 2.3).

Feature: incident-management, Property 3: Status changes follow the transition
state machine.

Validates: Requirements 3.1, 3.3, 7.3, 7.4.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.domain.models import IncidentStatus
from backend.domain.status_machine import is_valid_transition

# The only two transitions that must be accepted (design allow-list).
_EXPECTED_VALID: set[tuple[IncidentStatus, IncidentStatus]] = {
    (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING),
    (IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED),
}

_STATUS = st.sampled_from(list(IncidentStatus))


@settings(max_examples=200)
@given(current=_STATUS, target=_STATUS)
def test_only_forward_adjacent_transitions_are_valid(
    current: IncidentStatus, target: IncidentStatus
) -> None:
    """is_valid_transition returns True iff the pair is a Valid_Transition.

    Fuzzed across all generated (current, target) pairs; the expected result is
    membership in the design allow-list, so same-state, backward, and skip-ahead
    all return False.
    """
    assert is_valid_transition(current, target) == (
        (current, target) in _EXPECTED_VALID
    )


def test_exhaustive_over_all_nine_pairs() -> None:
    """Exhaustively enumerate all 9 (from, target) pairs.

    Exactly OPEN->INVESTIGATING and INVESTIGATING->RESOLVED are valid; the other
    seven (including same-state and backward) are rejected.
    """
    valid: set[tuple[IncidentStatus, IncidentStatus]] = set()
    for current in IncidentStatus:
        for target in IncidentStatus:
            if is_valid_transition(current, target):
                valid.add((current, target))
    assert valid == _EXPECTED_VALID
