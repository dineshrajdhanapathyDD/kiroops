"""Liveness endpoint test (Phase 2).

``GET /health`` is a lightweight check for API Gateway/Lambda that must not touch
any backend (no DynamoDB, no Bedrock). Verified against the default SQLite app
built with an injected in-memory connection.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.repository import db


def test_health_returns_ok() -> None:
    """GET /health returns 200 with the fixed liveness body."""
    conn = db.in_memory()
    try:
        client = TestClient(create_app(conn=conn))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        conn.close()
