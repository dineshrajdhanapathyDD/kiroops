"""RemediationRepository over DynamoDB (Phase 1).

Mirrors :class:`backend.repository.remediation_repository.RemediationRepository`
- same ``save_all`` / ``list`` methods. Each action is stored as an
``ACTION#<action_id>`` item under the incident partition. ``list`` queries the
incident partition for ``begins_with(SK, "ACTION#")``; because the action ids
are zero-padded (``ACT-0001``, ``ACT-0002``, ...) ascending sort-key order
matches the ``ORDER BY action_id ASC`` the SQLite version returns (Req 5.3).

Requirements: 5.3.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.domain.models import RemediationAction
from backend.repository import dynamo


def _item_to_action(item: dict[str, Any]) -> RemediationAction:
    """Reconstruct a ``RemediationAction`` from a stored ACTION item."""
    return RemediationAction(
        action_id=item["action_id"],
        incident_id=item["incident_id"],
        description=item["description"],
        rationale=item["rationale"],
    )


class DynamoRemediationRepository:
    """DynamoDB-backed persistence for remediation actions (Req 5.3)."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def save_all(self, actions: Iterable[RemediationAction]) -> None:
        """Persist all remediation actions (batched writes)."""
        with self._table.batch_writer() as batch:
            for action in actions:
                batch.put_item(
                    Item={
                        dynamo.PK: dynamo.incident_pk(action.incident_id),
                        dynamo.SK: dynamo.action_sk(action.action_id),
                        "action_id": action.action_id,
                        "incident_id": action.incident_id,
                        "description": action.description,
                        "rationale": action.rationale,
                    }
                )

    def list(self, incident_id: str) -> list[RemediationAction]:
        """Return the remediation actions for an incident (Req 5.3)."""
        from boto3.dynamodb.conditions import Key

        items: list[dict[str, Any]] = []
        condition = Key(dynamo.PK).eq(dynamo.incident_pk(incident_id)) & Key(
            dynamo.SK
        ).begins_with(dynamo.SK_ACTION_PREFIX)
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
        return [_item_to_action(item) for item in items]
