"""DynamoDB single-table accessor and table bootstrap (Phase 1).

This module is the only place that constructs a boto3 DynamoDB resource. It is
imported *only* on the DynamoDB persistence path (see ``repository.factory``);
the SQLite path never imports it, so the backend and its SQLite tests keep
running without boto3 installed. ``boto3`` is therefore imported at module top
here, which is acceptable because reaching this module already implies the
DynamoDB backend was selected.

Single-table design (all items in one table keyed by ``PK`` / ``SK``):

- Incident META:     PK="INCIDENT#<id>", SK="META"
- Timeline event:    PK="INCIDENT#<id>", SK="EVENT#<seq:05d>"
- Diagnosis:         PK="INCIDENT#<id>", SK="DIAGNOSIS"
- Remediation:       PK="INCIDENT#<id>", SK="ACTION#<action_id>"
- Incident counter:  PK="COUNTER",       SK="INCIDENT"
- Per-incident seq:  PK="INCIDENT#<id>", SK="COUNTER#EVENT"

A global secondary index ``GSI1`` (GSI1PK / GSI1SK) is projected only over
incident META items so ``list()`` can query all incidents ordered by id.

Requirements: 1.x-7.x storage boundary (mirrors the SQLite repositories).
"""

from __future__ import annotations

from typing import Any

import boto3

# Attribute and key names (single source of truth for the whole DDB backend).
PK = "PK"
SK = "SK"
GSI1_NAME = "GSI1"
GSI1PK = "GSI1PK"
GSI1SK = "GSI1SK"

# Constant partition value for the incident-list index. Only META items carry
# it, so the index contains exactly one entry per incident.
INCIDENT_GSI1PK = "INCIDENT"

# Sort-key sentinels / prefixes.
SK_META = "META"
SK_DIAGNOSIS = "DIAGNOSIS"
SK_EVENT_PREFIX = "EVENT#"
SK_ACTION_PREFIX = "ACTION#"
SK_EVENT_COUNTER = "COUNTER#EVENT"

# Incident id counter item coordinates.
COUNTER_PK = "COUNTER"
COUNTER_INCIDENT_SK = "INCIDENT"


def incident_pk(incident_id: str) -> str:
    """Partition key shared by every item belonging to one incident."""
    return f"INCIDENT#{incident_id}"


def event_sk(seq: int) -> str:
    """Sort key for a timeline event; zero-padded so lexical order == seq order."""
    return f"{SK_EVENT_PREFIX}{seq:05d}"


def action_sk(action_id: str) -> str:
    """Sort key for a remediation action item."""
    return f"{SK_ACTION_PREFIX}{action_id}"


def get_resource(region: str, endpoint_url: str | None = None) -> Any:
    """Return a boto3 DynamoDB *resource* for the given region.

    ``endpoint_url`` is optional and only used for local development against a
    DynamoDB-local endpoint; production reads credentials/region from the
    environment or instance role.
    """
    return boto3.resource(
        "dynamodb", region_name=region, endpoint_url=endpoint_url
    )


def get_table(table_name: str, region: str, endpoint_url: str | None = None) -> Any:
    """Return the boto3 ``Table`` for the configured single table."""
    return get_resource(region, endpoint_url).Table(table_name)


def create_table(table_name: str, region: str, endpoint_url: str | None = None) -> Any:
    """Create the single table with its ``GSI1`` index and return the ``Table``.

    Intended for tests (against moto) and local bootstrap. Uses on-demand
    (``PAY_PER_REQUEST``) billing so no throughput has to be specified. Waits
    until the table is active before returning.
    """
    resource = get_resource(region, endpoint_url)
    table = resource.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": PK, "KeyType": "HASH"},
            {"AttributeName": SK, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": PK, "AttributeType": "S"},
            {"AttributeName": SK, "AttributeType": "S"},
            {"AttributeName": GSI1PK, "AttributeType": "S"},
            {"AttributeName": GSI1SK, "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": GSI1_NAME,
                "KeySchema": [
                    {"AttributeName": GSI1PK, "KeyType": "HASH"},
                    {"AttributeName": GSI1SK, "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table
