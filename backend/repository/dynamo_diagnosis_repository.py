"""DiagnosisRepository over DynamoDB (Phase 1).

Mirrors :class:`backend.repository.diagnosis_repository.DiagnosisRepository` -
same ``save`` / ``get`` methods. A single diagnosis per incident is stored as
the ``DIAGNOSIS`` item; a later ``save`` overwrites it, matching the SQLite
"most recent wins" behavior that ``get`` relies on. ``evidence_refs`` is stored
as a native list and ``created_at`` as an ISO-8601 string, both rebuilt on read.

Requirements: 4.4.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.domain.models import Diagnosis
from backend.repository import dynamo


def _item_to_diagnosis(item: dict[str, Any]) -> Diagnosis:
    """Reconstruct a ``Diagnosis`` from a stored DIAGNOSIS item."""
    return Diagnosis(
        incident_id=item["incident_id"],
        summary=item["summary"],
        evidence_refs=list(item["evidence_refs"]),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


class DynamoDiagnosisRepository:
    """DynamoDB-backed persistence for incident diagnoses (Req 4.4)."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def save(self, diagnosis: Diagnosis) -> None:
        """Persist a diagnosis associated with an incident (Req 4.4)."""
        self._table.put_item(
            Item={
                dynamo.PK: dynamo.incident_pk(diagnosis.incident_id),
                dynamo.SK: dynamo.SK_DIAGNOSIS,
                "incident_id": diagnosis.incident_id,
                "summary": diagnosis.summary,
                "evidence_refs": list(diagnosis.evidence_refs),
                "created_at": diagnosis.created_at.isoformat(),
            }
        )

    def get(self, incident_id: str) -> Diagnosis | None:
        """Return the diagnosis for an incident, or ``None``."""
        response = self._table.get_item(
            Key={
                dynamo.PK: dynamo.incident_pk(incident_id),
                dynamo.SK: dynamo.SK_DIAGNOSIS,
            }
        )
        item = response.get("Item")
        return None if item is None else _item_to_diagnosis(item)
