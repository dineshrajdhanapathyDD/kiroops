"""Tests for the persistence switch, factory, and service composition (Phase 1).

Verifies that:
- ``config.get_persistence`` defaults to ``sqlite`` and validates its input.
- ``factory.build_from_config`` builds a DynamoDB bundle when selected.
- ``IncidentService`` runs unchanged over a DynamoDB repository bundle, proving
  the service layer is backend-agnostic (no business-logic change).

Requirements: storage-backend selection + backend-agnostic service layer.
"""

from __future__ import annotations

import pytest

from backend import config
from backend.domain.models import IncidentStatus, Severity
from backend.repository import dynamo, factory
from backend.service.incident_service import IncidentService
from backend.tests.dynamo_support import TEST_REGION, fresh_table


def test_get_persistence_defaults_to_sqlite() -> None:
    assert config.get_persistence({}) == config.PERSISTENCE_SQLITE


def test_get_persistence_reads_dynamodb() -> None:
    env = {config.ENV_PERSISTENCE: "dynamodb"}
    assert config.get_persistence(env) == config.PERSISTENCE_DYNAMODB


def test_get_persistence_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        config.get_persistence({config.ENV_PERSISTENCE: "postgres"})


def test_dynamo_config_from_env_uses_defaults() -> None:
    cfg = config.DynamoConfig.from_env({config.ENV_AWS_REGION: "eu-west-1"})
    assert cfg.table_name == config.DEFAULT_DDB_TABLE
    assert cfg.region == "eu-west-1"


def test_build_from_config_builds_dynamodb_bundle() -> None:
    with fresh_table() as table:
        table_name = table.name
        env = {
            config.ENV_PERSISTENCE: "dynamodb",
            config.ENV_DDB_TABLE: table_name,
            config.ENV_AWS_REGION: TEST_REGION,
        }
        # build_from_config resolves its own Table via get_table; it must land
        # on the same moto table created above (same mock_aws scope).
        bundle = factory.build_from_config(env=env)
        created = bundle.incidents.create(
            "x", Severity.LOW, "svc", _now()
        )
        assert created.incident_id == "INC-0001"
        assert bundle.incidents.get("INC-0001") == created


def test_incident_service_runs_over_dynamodb_bundle() -> None:
    with fresh_table() as table:
        bundle = factory.build_dynamodb(table)
        service = IncidentService.from_repositories(bundle)

        incident = service.create("db outage", Severity.HIGH, "payments")
        assert incident.status is IncidentStatus.OPEN

        # The "created" timeline event was appended via the same backend.
        detail = service.get(incident.incident_id)
        assert detail.incident.incident_id == incident.incident_id
        assert len(detail.timeline) == 1
        assert detail.timeline[0].type.value == "created"

        # A valid status transition is persisted and recorded.
        updated = service.update_status(
            incident.incident_id, IncidentStatus.INVESTIGATING
        )
        assert updated.status is IncidentStatus.INVESTIGATING
        detail = service.get(incident.incident_id)
        assert detail.incident.status is IncidentStatus.INVESTIGATING
        assert len(detail.timeline) == 2


def _now():
    from datetime import datetime, timezone

    return datetime(2024, 1, 1, tzinfo=timezone.utc)
