"""TimelineRepository over DynamoDB (Phase 1).

Mirrors :class:`backend.repository.timeline_repository.TimelineRepository` -
same public methods (``append`` and ``list`` only, no update/delete) so the
timeline stays append-only at the storage boundary (Req 6.2).

Ordering and append-safety are enforced with DynamoDB primitives instead of
SQLite:

- ``append`` derives the next per-incident ``seq`` from a dedicated counter item
  (PK="INCIDENT#<id>", SK="COUNTER#EVENT") via ``UpdateItem ADD ...
  ReturnValues=UPDATED_NEW``, then ``PutItem`` the ``EVENT#<seq:05d>`` item with
  ``attribute_not_exists(SK)`` so an event is never overwritten (Property 4).
- ``list`` queries the incident partition for ``begins_with(SK, "EVENT#")``.
  Because the seq is zero-padded, ascending sort-key order equals ascending seq
  order, which is chronological append order (Property 5 / Req 6.3).

Requirements: 6.1, 6.2, 6.3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.domain.models import TimelineEvent, TimelineEventType
from backend.repository import dynamo


def _item_to_event(item: dict[str, Any]) -> TimelineEvent:
    """Reconstruct a ``TimelineEvent`` from a stored EVENT item.

    ``seq`` is stored as a DynamoDB number (Decimal) and converted back to int;
    ``timestamp`` round-trips through ISO-8601 and ``details`` as a native map.
    """
    return TimelineEvent(
        incident_id=item["incident_id"],
        seq=int(item["seq"]),
        type=TimelineEventType(item["type"]),
        timestamp=datetime.fromisoformat(item["timestamp"]),
        details=dict(item["details"]),
    )


class DynamoTimelineRepository:
    """Append-only DynamoDB persistence for timeline events (Req 6.1-6.3)."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def _next_seq(self, incident_id: str) -> int:
        """Atomically increment and return the incident's event counter."""
        response = self._table.update_item(
            Key={
                dynamo.PK: dynamo.incident_pk(incident_id),
                dynamo.SK: dynamo.SK_EVENT_COUNTER,
            },
            UpdateExpression="ADD #v :one",
            ExpressionAttributeNames={"#v": "value"},
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"]["value"])

    def append(
        self,
        incident_id: str,
        type: TimelineEventType,
        timestamp: datetime,
        details: dict,
    ) -> None:
        """Append a new event, assigning the next per-incident ``seq``.

        The seq is taken from the per-incident atomic counter, then the event is
        written with a condition that its sort key does not already exist, so an
        append never overwrites an existing event (Req 6.2). ``details`` is
        stored as a native DynamoDB map.
        """
        next_seq = self._next_seq(incident_id)
        self._table.put_item(
            Item={
                dynamo.PK: dynamo.incident_pk(incident_id),
                dynamo.SK: dynamo.event_sk(next_seq),
                "incident_id": incident_id,
                "seq": next_seq,
                "type": type.value,
                "timestamp": timestamp.isoformat(),
                "details": details,
            },
            ConditionExpression="attribute_not_exists(SK)",
        )

    def list(self, incident_id: str) -> list[TimelineEvent]:
        """Return the incident's events earliest -> latest (Req 6.3).

        Ordered by ascending sort key == ascending ``seq`` == append order.
        """
        from boto3.dynamodb.conditions import Key

        items: list[dict[str, Any]] = []
        condition = Key(dynamo.PK).eq(dynamo.incident_pk(incident_id)) & Key(
            dynamo.SK
        ).begins_with(dynamo.SK_EVENT_PREFIX)
        response = self._table.query(
            KeyConditionExpression=condition, ScanIndexForward=True
        )
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self._table.query(
                KeyConditionExpression=condition,
                ScanIndexForward=True,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return [_item_to_event(item) for item in items]
