"""Integration tests for the incident API and error table (Task 7.4).

Uses ``fastapi.testclient.TestClient`` against an app wired to a fresh in-memory
SQLite ``IncidentService`` (isolated per test). Covers each row of the design's
error table plus the happy paths for create/list/get/status.

Requirements: 1.6, 1.7, 2.3, 3.3, 3.4.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.repository import db
from backend.service.incident_service import IncidentService

_INC_ID_PATTERN = re.compile(r"^INC-\d{4,}$")


@pytest.fixture()
def client() -> TestClient:
    """A TestClient over an app with a fresh in-memory, bootstrapped DB."""
    conn = db.in_memory()
    app = create_app(service=IncidentService(conn))
    with TestClient(app) as test_client:
        yield test_client
    conn.close()


def _create(client: TestClient, **overrides) -> dict:
    payload = {"title": "db outage", "severity": "HIGH", "service": "payments"}
    payload.update(overrides)
    return client.post("/incidents", json=payload)


# --- Happy paths -------------------------------------------------------------


def test_create_returns_201_with_open_incident_and_inc_id(client: TestClient) -> None:
    """POST /incidents returns 201, an INC-#### id, and OPEN status (Req 1.1)."""
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert _INC_ID_PATTERN.match(body["incident_id"])
    assert body["status"] == "OPEN"
    assert body["title"] == "db outage"
    assert body["severity"] == "HIGH"
    assert body["service"] == "payments"
    assert body["created_at"]  # ISO string present


def test_list_returns_created_incidents(client: TestClient) -> None:
    """GET /incidents returns the created incidents as summaries (Req 2.1)."""
    id_a = _create(client, title="a").json()["incident_id"]
    id_b = _create(client, title="b").json()["incident_id"]

    resp = client.get("/incidents")
    assert resp.status_code == 200
    ids = [row["incident_id"] for row in resp.json()]
    assert ids == [id_a, id_b]


def test_get_returns_incident_with_created_timeline(client: TestClient) -> None:
    """GET /incidents/{id} returns the incident and its timeline (Req 2.2)."""
    incident_id = _create(client).json()["incident_id"]

    resp = client.get(f"/incidents/{incident_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident_id"] == incident_id
    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["type"] == "created"
    assert body["timeline"][0]["timestamp"]


def test_valid_patch_advances_status_and_records_event(client: TestClient) -> None:
    """A valid PATCH advances status and appends a status changed event (Req 3.1, 3.2)."""
    incident_id = _create(client).json()["incident_id"]

    resp = client.patch(
        f"/incidents/{incident_id}/status", json={"status": "INVESTIGATING"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "INVESTIGATING"

    detail = client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "INVESTIGATING"
    last = detail["timeline"][-1]
    assert last["type"] == "status changed"
    assert last["details"] == {"from": "OPEN", "to": "INVESTIGATING"}


# --- Error table -------------------------------------------------------------


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_empty_or_whitespace_title_returns_422_field_title(
    client: TestClient, title: str
) -> None:
    """Empty/whitespace title -> 422 envelope naming title (Req 1.6)."""
    resp = _create(client, title=title)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["field"] == "title"
    assert "message" in error and "code" in error


def test_invalid_severity_returns_422_field_severity(client: TestClient) -> None:
    """Unknown severity -> 422 envelope naming severity (Req 1.7)."""
    resp = _create(client, severity="SEVERE")
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["field"] == "severity"


def test_get_unknown_id_returns_404(client: TestClient) -> None:
    """GET unknown incident id -> 404 envelope (Req 2.3)."""
    resp = client.get("/incidents/INC-9999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_patch_unknown_id_returns_404(client: TestClient) -> None:
    """PATCH unknown incident id -> 404 envelope (Req 2.3)."""
    resp = client.patch("/incidents/INC-9999/status", json={"status": "INVESTIGATING"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_invalid_transition_returns_409_and_preserves_status(
    client: TestClient,
) -> None:
    """Skip-ahead OPEN -> RESOLVED -> 409; status unchanged when re-fetched (Req 3.3, 7.4)."""
    incident_id = _create(client).json()["incident_id"]

    resp = client.patch(
        f"/incidents/{incident_id}/status", json={"status": "RESOLVED"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_transition"

    detail = client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "OPEN"
    assert all(e["type"] != "status changed" for e in detail["timeline"])


def test_backward_transition_returns_409_and_preserves_status(
    client: TestClient,
) -> None:
    """Backward INVESTIGATING -> OPEN -> 409; status unchanged (Req 3.3, 7.4)."""
    incident_id = _create(client).json()["incident_id"]
    client.patch(f"/incidents/{incident_id}/status", json={"status": "INVESTIGATING"})

    resp = client.patch(f"/incidents/{incident_id}/status", json={"status": "OPEN"})
    assert resp.status_code == 409

    detail = client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "INVESTIGATING"


def test_unknown_status_value_returns_422(client: TestClient) -> None:
    """Unknown status value in the body -> 422; no state change (Req 3.4)."""
    incident_id = _create(client).json()["incident_id"]

    resp = client.patch(
        f"/incidents/{incident_id}/status", json={"status": "CLOSED"}
    )
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"

    detail = client.get(f"/incidents/{incident_id}").json()
    assert detail["status"] == "OPEN"
