"""End-to-end app test over the DynamoDB persistence backend (Phase 2).

Proves that ``create_app()`` with no injection wires the full API to the
DynamoDB repositories when ``KIROOPS_PERSISTENCE=dynamodb`` is set, using moto's
in-memory ``mock_aws`` so no real AWS access is needed. The table is created via
the same :func:`backend.repository.dynamo.create_table` helper the Phase 1
bootstrap and repository tests use.

Env vars are set with ``monkeypatch`` so they are restored automatically after
the test, keeping the rest of the suite on the SQLite default.

Covers: create -> 201 INC-#### + OPEN; get -> includes timeline; list -> returns
it; PATCH valid transition -> 200; PATCH invalid -> 409 with status preserved;
diagnosis with the default provider -> 503 (LLM unavailable) with status
unchanged. Requirements: 1.1, 2.1, 2.2, 3.1, 3.3, 4.5, 7.4 over the DynamoDB
storage boundary.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from backend import config
from backend.api.app import create_app
from backend.repository import dynamo

TEST_REGION = "us-east-1"


@pytest.fixture
def dynamo_client(monkeypatch: pytest.MonkeyPatch):
    """Yield a TestClient wired to a fresh moto DynamoDB table via config only.

    Sets the persistence env vars, creates the single table inside ``mock_aws``,
    then builds the app with no injection so it must resolve the table through
    ``config`` + ``factory.build_from_config`` (the production wiring path).
    """
    table_name = f"kiroops-app-{uuid.uuid4().hex}"
    monkeypatch.setenv(config.ENV_PERSISTENCE, config.PERSISTENCE_DYNAMODB)
    monkeypatch.setenv(config.ENV_DDB_TABLE, table_name)
    monkeypatch.setenv(config.ENV_LLM_REGION, TEST_REGION)

    with mock_aws():
        dynamo.create_table(table_name, TEST_REGION)
        app = create_app()  # no injection: reads config, builds DynamoDB bundle
        yield TestClient(app)


def _create_incident(client: TestClient) -> dict:
    resp = client.post(
        "/incidents",
        json={"title": "checkout failing", "severity": "HIGH", "service": "payments"},
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_returns_well_formed_id_and_open_status(dynamo_client: TestClient) -> None:
    """POST /incidents persists to DynamoDB and returns INC-#### with OPEN (Req 1.1)."""
    body = _create_incident(dynamo_client)
    assert body["incident_id"].startswith("INC-")
    assert len(body["incident_id"]) >= 8  # "INC-" + at least 4 digits
    assert body["incident_id"][4:].isdigit()
    assert body["status"] == "OPEN"


def test_get_includes_timeline(dynamo_client: TestClient) -> None:
    """GET /incidents/{id} returns the incident with its created event (Req 2.2)."""
    incident_id = _create_incident(dynamo_client)["incident_id"]
    detail = dynamo_client.get(f"/incidents/{incident_id}").json()
    assert detail["incident_id"] == incident_id
    types = [e["type"] for e in detail["timeline"]]
    assert "created" in types


def test_list_returns_created_incident(dynamo_client: TestClient) -> None:
    """GET /incidents lists the persisted incident (Req 2.1)."""
    incident_id = _create_incident(dynamo_client)["incident_id"]
    resp = dynamo_client.get("/incidents")
    assert resp.status_code == 200
    assert incident_id in [i["incident_id"] for i in resp.json()]


def test_valid_transition_returns_200(dynamo_client: TestClient) -> None:
    """PATCH a valid transition (OPEN -> INVESTIGATING) returns 200 (Req 3.1)."""
    incident_id = _create_incident(dynamo_client)["incident_id"]
    resp = dynamo_client.patch(
        f"/incidents/{incident_id}/status", json={"status": "INVESTIGATING"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "INVESTIGATING"


def test_invalid_transition_returns_409_and_preserves_status(
    dynamo_client: TestClient,
) -> None:
    """PATCH an invalid transition (OPEN -> RESOLVED) -> 409, status unchanged (Req 3.3, 7.4)."""
    incident_id = _create_incident(dynamo_client)["incident_id"]
    resp = dynamo_client.patch(
        f"/incidents/{incident_id}/status", json={"status": "RESOLVED"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_transition"

    detail = dynamo_client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "OPEN"


def test_diagnosis_default_provider_returns_503_and_preserves_status(
    dynamo_client: TestClient,
) -> None:
    """Default (unavailable) LLM -> 503 and incident status unchanged (Req 4.5)."""
    incident_id = _create_incident(dynamo_client)["incident_id"]
    resp = dynamo_client.post(f"/incidents/{incident_id}/diagnosis")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "diagnosis_unavailable"

    detail = dynamo_client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "OPEN"
    assert all(e["type"] != "actions suggested" for e in detail["timeline"])
