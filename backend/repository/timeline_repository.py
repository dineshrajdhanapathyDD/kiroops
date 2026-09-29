"""TimelineRepository over SQLite (Task 4.3).

The timeline is modeled append-only: this repository exposes exactly ``append``
and ``list`` and offers no update or delete method, so prior events can never be
modified or removed (Req 6.2). Each append computes ``seq = max(existing) + 1``
inside a transaction, and ``list`` returns events ordered by ``timestamp`` then
``seq`` (earliest -> latest, Req 6.3) which gives a stable order for events that
share a timestamp.

Requirements: 6.1, 6.2, 6.3.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from backend.domain.models import TimelineEvent, TimelineEventType


def _row_to_event(row: sqlite3.Row) -> TimelineEvent:
    """Reconstruct a ``TimelineEvent`` from a stored row.

    ``timestamp`` round-trips through ISO-8601 and ``details`` through JSON text.
    """
    return TimelineEvent(
        incident_id=row["incident_id"],
        seq=row["seq"],
        type=TimelineEventType(row["type"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
        details=json.loads(row["details"]),
    )


class TimelineRepository:
    """Append-only persistence for incident timeline events (Req 6.1-6.3)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(
        self,
        incident_id: str,
        type: TimelineEventType,
        timestamp: datetime,
        details: dict,
    ) -> None:
        """Append a new event, assigning the next per-incident ``seq``.

        The next ``seq`` is derived from the current maximum for the incident
        inside the same transaction as the insert, so appends never overwrite an
        existing event (Req 6.2). ``details`` is stored as JSON text.
        """
        try:
            row = self._conn.execute(
                "SELECT MAX(seq) AS max_seq FROM timeline_events "
                "WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            current_max = row["max_seq"]
            next_seq = 1 if current_max is None else current_max + 1
            self._conn.execute(
                "INSERT INTO timeline_events "
                "(incident_id, seq, type, timestamp, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    incident_id,
                    next_seq,
                    type.value,
                    timestamp.isoformat(),
                    json.dumps(details),
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def list(self, incident_id: str) -> list[TimelineEvent]:
        """Return the incident's events earliest -> latest (Req 6.3).

        Ordered by ``timestamp`` then ``seq`` so events sharing a timestamp keep
        their append order.
        """
        rows = self._conn.execute(
            "SELECT incident_id, seq, type, timestamp, details "
            "FROM timeline_events WHERE incident_id = ? "
            "ORDER BY timestamp ASC, seq ASC",
            (incident_id,),
        ).fetchall()
        return [_row_to_event(row) for row in rows]
