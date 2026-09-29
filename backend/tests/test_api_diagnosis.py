"""Integration tests for the diagnosis flow (Task 10.6).

Uses ``fastapi.testclient.TestClient`` against an app wired to a fresh in-memory
SQLite database with a stub LLM injected via ``create_app(conn=..., llm=...)``.
Covers the success path (200 with summary + actions, timeline events appended,
GET remediation-actions) and the unavailable path (503 + status unchanged).

Requirements: 4.3, 4.4, 4.5, 5.2, 5.3.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.agent.provider import LlmResult, LlmUnavailableError
from backend.api.app import create_app
from backend.repository import db


class SuccessLlm:
    """Stub provider returning canned diagnosis text (success path)."""

    def complete(self, prompt: str) -> LlmResult:
        return LlmResult(text="root cause: connection pool exhausted")


class UnavailableLlm:
    """Stub provider that always raises (unavailable path, Req 4.5)."""

    def complete(self, prompt: str) -> LlmResult:
        raise LlmUnavailableError("stub unavailable")


def _make_client(llm) -> tuple[TestClient, "db.sqlite3.Connection"]:
    conn = db.in_memory()
    app = create_app(conn=conn, llm=llm)
    return TestClient(app), conn


def _create_incident(client: TestClient) -> str:
    resp = client.post(
        "/incidents",
        json={"title": "checkout failing", "severity": "HIGH", "service": "payments"},
    )
    assert resp.status_code == 201
    return resp.json()["incident_id"]


def test_diagnosis_success_returns_summary_and_actions() -> None:
    """POST diagnosis returns 200 with summary and remediation actions (Req 4.2, 5.1)."""
    client, conn = _make_client(SuccessLlm())
    try:
        incident_id = _create_incident(client)

        resp = client.post(f"/incidents/{incident_id}/diagnosis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["incident_id"] == incident_id
        assert body["summary"] == "root cause: connection pool exhausted"
        assert body["evidence_refs"]  # references gathered evidence
        assert len(body["remediation_actions"]) >= 1
        first = body["remediation_actions"][0]
        assert first["action_id"].startswith("ACT-")
        assert first["description"]
        assert first["rationale"]
    finally:
        conn.close()


def test_diagnosis_success_appends_timeline_events() -> None:
    """"diagnosis requested" and "actions suggested" events are appended (Req 4.3, 5.2)."""
    client, conn = _make_client(SuccessLlm())
    try:
        incident_id = _create_incident(client)
        client.post(f"/incidents/{incident_id}/diagnosis")

        detail = client.get(f"/incidents/{incident_id}").json()
        types = [e["type"] for e in detail["timeline"]]
        assert "diagnosis requested" in types
        assert "actions suggested" in types
        # Ordering: requested comes before suggested.
        assert types.index("diagnosis requested") < types.index("actions suggested")
    finally:
        conn.close()


def test_get_remediation_actions_returns_persisted_actions() -> None:
    """GET remediation-actions returns the persisted actions (Req 5.3)."""
    client, conn = _make_client(SuccessLlm())
    try:
        incident_id = _create_incident(client)
        posted = client.post(f"/incidents/{incident_id}/diagnosis").json()

        resp = client.get(f"/incidents/{incident_id}/remediation-actions")
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) == len(posted["remediation_actions"])
        # Ids returned by POST match those retrieved via GET.
        assert [a["action_id"] for a in actions] == [
            a["action_id"] for a in posted["remediation_actions"]
        ]
    finally:
        conn.close()


def test_diagnosis_unavailable_returns_503_and_preserves_status() -> None:
    """Unavailable LLM -> 503; incident status unchanged when re-fetched (Req 4.5)."""
    client, conn = _make_client(UnavailableLlm())
    try:
        incident_id = _create_incident(client)

        resp = client.post(f"/incidents/{incident_id}/diagnosis")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "diagnosis_unavailable"

        detail = client.get(f"/incidents/{incident_id}").json()
        assert detail["status"] == "OPEN"
        # No "actions suggested" event since no diagnosis was produced.
        assert all(e["type"] != "actions suggested" for e in detail["timeline"])
    finally:
        conn.close()


def test_diagnosis_unknown_incident_returns_404() -> None:
    """POST diagnosis for an unknown incident -> 404 (Req 2.3)."""
    client, conn = _make_client(SuccessLlm())
    try:
        resp = client.post("/incidents/INC-9999/diagnosis")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
    finally:
        conn.close()
