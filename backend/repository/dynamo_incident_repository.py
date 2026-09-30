"""IncidentRepository over DynamoDB (Phase 1).

Mirrors :class:`backend.repository.incident_repository.IncidentRepository`
exactly - same public methods and behavior - but stores incidents as ``META``
items in the single table and enforces the id invariants with an atomic counter
instead of SQLite AUTOINCREMENT:

- ``create`` runs an ``UpdateItem`` ``ADD`` on the (COUNTER, INCIDENT) item with
  ``ReturnValues=UPDATED_NEW`` to obtain the next integer atomically, then
  derives ``incident_id = "INC-" + zfill(4)``. Concurrent creates therefore get
  distinct, strictly increasing numbers (Property 2 / Req 1.2, 1.3, 7.1, 7.2).
- ``list`` queries ``GSI1`` (constant partition ``INCIDENT``) so only incident
  META items are returned, ordered by ``incident_id`` ascending (Req 2.1).

Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 7.1, 7.2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.domain.models import Incident, IncidentStatus, Severity
from backend.repository import dynamo


def _incident_id_for(num: int) -> str:
    """Derive the displayed incident id from the numeric counter value.

    ``zfill(4)`` is a minimum width, so ids beyond 9999 keep growing in length
    while remaining monotonic (e.g. ``INC-10000``), matching ``INC-\\d{4,}``.
    """
    return "INC-" + str(num).zfill(4)


def _item_to_incident(item: dict[str, Any]) -> Incident:
    """Reconstruct an ``Incident`` from a stored META item.

    ``created_at`` round-trips through ISO-8601; enums are rebuilt from their
    string values.
    """
    return Incident(
        incident_id=item["incident_id"],
        title=item["title"],
        severity=Severity(item["severity"]),
        service=item["service"],
        status=IncidentStatus(item["status"]),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


class DynamoIncidentRepository:
    """DynamoDB-backed persistence for incidents (Req 1.1, 2.1, 2.2, 3.1)."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def _next_incident_number(self) -> int:
        """Atomically increment and return the global incident counter."""
        response = self._table.update_item(
            Key={dynamo.PK: dynamo.COUNTER_PK, dynamo.SK: dynamo.COUNTER_INCIDENT_SK},
            UpdateExpression="ADD #v :one",
            ExpressionAttributeNames={"#v": "value"},
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        # DynamoDB returns numbers as Decimal; convert back to a plain int.
        return int(response["Attributes"]["value"])

    def create(
        self,
        title: str,
        severity: Severity,
        service: str,
        created_at: datetime,
    ) -> Incident:
        """Insert an incident and assign its ``INC-####`` id atomically.

        The next number is taken from the atomic counter and the derived id is
        used as the META item's key, so assigned ids are unique and monotonic
        (Req 1.2, 1.3, 7.1, 7.2).
        """
        status = IncidentStatus.OPEN
        num = self._next_incident_number()
        incident_id = _incident_id_for(num)
        self._table.put_item(
            Item={
                dynamo.PK: dynamo.incident_pk(incident_id),
                dynamo.SK: dynamo.SK_META,
                dynamo.GSI1PK: dynamo.INCIDENT_GSI1PK,
                dynamo.GSI1SK: incident_id,
                "incident_id": incident_id,
                "title": title,
                "severity": severity.value,
                "service": service,
                "status": status.value,
                "created_at": created_at.isoformat(),
            }
        )
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
        response = self._table.get_item(
            Key={dynamo.PK: dynamo.incident_pk(incident_id), dynamo.SK: dynamo.SK_META}
        )
        item = response.get("Item")
        return None if item is None else _item_to_incident(item)

    def list(self) -> list[Incident]:
        """Return all incidents ordered by id ascending via ``GSI1`` (Req 2.1)."""
        from boto3.dynamodb.conditions import Key

        items: list[dict[str, Any]] = []
        response = self._table.query(
            IndexName=dynamo.GSI1_NAME,
            KeyConditionExpression=Key(dynamo.GSI1PK).eq(dynamo.INCIDENT_GSI1PK),
            ScanIndexForward=True,
        )
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self._table.query(
                IndexName=dynamo.GSI1_NAME,
                KeyConditionExpression=Key(dynamo.GSI1PK).eq(dynamo.INCIDENT_GSI1PK),
                ScanIndexForward=True,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return [_item_to_incident(item) for item in items]

    def update_status(self, incident_id: str, new_status: IncidentStatus) -> None:
        """Persist a new status for an existing incident (Req 3.1).

        Transition validity is the service layer's responsibility; this method
        only writes the value it is given.
        """
        self._table.update_item(
            Key={dynamo.PK: dynamo.incident_pk(incident_id), dynamo.SK: dynamo.SK_META},
            UpdateExpression="SET #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": new_status.value},
        )
