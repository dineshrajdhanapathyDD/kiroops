"""RemediationRepository over SQLite (Task 4.6).

Persists the ``RemediationAction`` set derived from a diagnosis. ``save_all``
writes the actions for an incident in one transaction; ``list`` returns them for
retrieval (Req 5.3).

Requirements: 5.3.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from backend.domain.models import RemediationAction


def _row_to_action(row: sqlite3.Row) -> RemediationAction:
    """Reconstruct a ``RemediationAction`` from a stored row."""
    return RemediationAction(
        action_id=row["action_id"],
        incident_id=row["incident_id"],
        description=row["description"],
        rationale=row["rationale"],
    )


class RemediationRepository:
    """Persistence for remediation actions (Req 5.3)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_all(self, actions: Iterable[RemediationAction]) -> None:
        """Persist all remediation actions in a single transaction."""
        rows = [
            (a.action_id, a.incident_id, a.description, a.rationale)
            for a in actions
        ]
        try:
            self._conn.executemany(
                "INSERT INTO remediation_actions "
                "(action_id, incident_id, description, rationale) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def list(self, incident_id: str) -> list[RemediationAction]:
        """Return the remediation actions for an incident (Req 5.3)."""
        rows = self._conn.execute(
            "SELECT action_id, incident_id, description, rationale "
            "FROM remediation_actions WHERE incident_id = ? "
            "ORDER BY action_id ASC",
            (incident_id,),
        ).fetchall()
        return [_row_to_action(row) for row in rows]
