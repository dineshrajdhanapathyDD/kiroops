"""Pure status state machine (Task 2.2).

This module is the sole authority for incident status transitions. It is a pure
function over an explicit allow-list of forward-adjacent transitions; it performs
no I/O and holds no state, so it is exhaustively testable in isolation.

Requirements: 3.1, 3.3, 7.3, 7.4.
"""

from __future__ import annotations

from backend.domain.models import IncidentStatus

# The exactly-two Valid_Transitions (Req 3.1, 7.3). Anything not in this set is
# rejected: same-state (OPEN->OPEN), backward (RESOLVED->INVESTIGATING), and
# skip-ahead (OPEN->RESOLVED).
_VALID_TRANSITIONS: frozenset[tuple[IncidentStatus, IncidentStatus]] = frozenset(
    {
        (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING),
        (IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED),
    }
)


def is_valid_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    """Return True only for forward-adjacent transitions.

    Rejects same-state, backward, skip-ahead (OPEN->RESOLVED), and any transition
    not in the allow-list (Req 3.3, 7.3, 7.4).
    """
    return (current, target) in _VALID_TRANSITIONS
