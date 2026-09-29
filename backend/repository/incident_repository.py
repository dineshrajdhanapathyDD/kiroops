"""IncidentRepository over SQLite (Task 4.1).

The repository is the only code that touches the ``incidents`` table. It owns its
transactions and enforces the incident-id invariants at the storage boundary:

- ``num`` is ``INTEGER PRIMARY KEY AUTOINCREMENT``, so SQLite hands out a strictly
  increasing, never-reused numeric sequence (monotonic numeric portion, Req 1.3).
- ``incident_id`` is derived deterministically as ``"INC-" + str(num).zfill(4)``
  inside the same transaction as the insert, so concurrent creates cannot observe
  or reuse the same ``num`` (Req 1.2, 7.1, 7.2).
- A ``UNIQUE`` constraint on ``incident_id`` (see ``db.SCHEMA_DDL``) is a
  defense-in-depth guard.

Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 7.1, 7.2.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from backend.domain.models import Incident, IncidentStatus, Severity


def _incident_id_for(num: int) -> str:
    """Derive the displayed incident id from the numeric primary key.

    ``zfill(4)`` is a minimum width, so ids beyond 9999 keep growing in length
    while remaining monotonic (e.g. ``INC-10000``), matching ``INC-\\d{4,}``.
    """
    return "INC-" + str(num).zfill(4)


def _row_to_incident(row: sqlite3.Row) -> Incident:
    """Reconstruct an ``Incident`` from a stored row.

    ``created_at`` is stored as an ISO-8601 string and rebuilt into a
    ``datetime`` so the value round-trips.
    """
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        severity=Severity(row["severity"]),
        service=row["service"],
        status=IncidentStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class IncidentRepository:
    """Persistence for incidents (Req 1.1, 2.1, 2.2, 3.1)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        title: str,
        severity: Severity,
        service: str,
        created_at: datetime,
    ) -> Incident:
        """Insert an incident and assign its ``INC-####`` id atomically.

        The row is inserted with a placeholder id, the AUTOINCREMENT ``num`` is
        read back via ``lastrowid``, the real ``incident_id`` is derived and
        persisted, and the whole sequence is committed as one transaction so the
        assigned id is unique and monotonic (Req 1.2, 1.3, 7.1, 7.2).
        """
        status = IncidentStatus.OPEN
        try:
            cur = self._conn.execute(
                "INSERT INTO incidents "
                "(incident_id, title, severity, service, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "",  # placeholder, replaced below inside the same transaction
                    title,
                    severity.value,
                    service,
                    status.value,
                    created_at.isoformat(),
                ),
            )
            num = int(cur.lastrowid)
            incident_id = _incident_id_for(num)
            self._conn.execute(
                "UPDATE incidents SET incident_id = ? WHERE num = ?",
                (incident_id, num),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return Incident(
            incident_id=incident_id,
            title=title,
            severity=severity,
            service=service,
            status=status,
            created_at=created_at,
        )

    def get(self, incident_id: str) -> Incident | None:
        """Return the incident with ``incident_id`` or ``None`` (Req 2.2, 2.3)."""
        row = self._conn.execute(
            "SELECT incident_id, title, severity, service, status, created_at "
            "FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        return None if row is None else _row_to_incident(row)

    def list(self) -> list[Incident]:
        """Return all incidents in creation order (Req 2.1)."""
        rows = self._conn.execute(
            "SELECT incident_id, title, severity, service, status, created_at "
            "FROM incidents ORDER BY num ASC"
        ).fetchall()
        return [_row_to_incident(row) for row in rows]

    def update_status(self, incident_id: str, new_status: IncidentStatus) -> None:
        """Persist a new status for an existing incident (Req 3.1).

        Transition validity is the service layer's responsibility; this method
        only writes the value it is given.
        """
        try:
            self._conn.execute(
                "UPDATE incidents SET status = ? WHERE incident_id = ?",
                (new_status.value, incident_id),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
