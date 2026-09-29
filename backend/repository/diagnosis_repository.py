"""DiagnosisRepository over SQLite (Task 4.6).

Persists the evidence-based ``Diagnosis`` produced for an incident. ``evidence_refs``
is stored as a JSON array and ``created_at`` as an ISO-8601 string, both rebuilt
on read so the value round-trips.

Requirements: 4.4.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from backend.domain.models import Diagnosis


def _row_to_diagnosis(row: sqlite3.Row) -> Diagnosis:
    """Reconstruct a ``Diagnosis`` from a stored row."""
    return Diagnosis(
        incident_id=row["incident_id"],
        summary=row["summary"],
        evidence_refs=json.loads(row["evidence_refs"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class DiagnosisRepository:
    """Persistence for incident diagnoses (Req 4.4)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, diagnosis: Diagnosis) -> None:
        """Persist a diagnosis associated with an incident (Req 4.4)."""
        try:
            self._conn.execute(
                "INSERT INTO diagnoses "
                "(incident_id, summary, evidence_refs, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    diagnosis.incident_id,
                    diagnosis.summary,
                    json.dumps(diagnosis.evidence_refs),
                    diagnosis.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def get(self, incident_id: str) -> Diagnosis | None:
        """Return the most recent diagnosis for an incident, or ``None``."""
        row = self._conn.execute(
            "SELECT incident_id, summary, evidence_refs, created_at "
            "FROM diagnoses WHERE incident_id = ? ORDER BY id DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        return None if row is None else _row_to_diagnosis(row)
