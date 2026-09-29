"""FastAPI application and incident routers (Tasks 7.2, 7.3).

The API layer only validates request shapes, calls ``IncidentService``,
serializes responses, and maps domain errors to the shared envelope (handlers
live in ``api.errors``). No business logic lives here.

Service injection: ``create_app`` accepts either a ready ``IncidentService`` or a
``sqlite3.Connection`` to build one over. Tests pass a fresh in-memory,
bootstrapped connection (or a pre-built service), so each test gets an isolated
database. The service is stored on ``app.state`` and provided to routes through
the ``get_service`` dependency, which can also be overridden via
``app.dependency_overrides`` if desired.

Endpoints (design.md):
    POST   /incidents                       -> 201 IncidentResponse
    GET    /incidents                       -> 200 list[IncidentSummary]
    GET    /incidents/{incident_id}         -> 200 IncidentDetailResponse
    PATCH  /incidents/{incident_id}/status  -> 200 IncidentResponse

Requirements: 1.1, 1.6, 1.7, 2.1, 2.2, 2.3, 3.1, 3.3, 3.4, 7.4.
"""

from __future__ import annotations

import sqlite3

from fastapi import Depends, FastAPI, status

from backend.api.errors import register_exception_handlers
from backend.api.models import (
    CreateIncidentRequest,
    IncidentDetailResponse,
    IncidentResponse,
    IncidentSummary,
    UpdateStatusRequest,
)
from backend.repository import db
from backend.service.incident_service import IncidentService


def get_service() -> IncidentService:
    """Dependency placeholder; replaced per-app by ``create_app``.

    The real provider is bound in ``create_app`` so the service (and its
    connection) is created once and shared. Declaring it here gives routes a
    stable dependency symbol that can also be overridden in tests via
    ``app.dependency_overrides[get_service]``.
    """
    raise RuntimeError("IncidentService dependency is not configured.")


def create_app(
    service: IncidentService | None = None,
    conn: sqlite3.Connection | None = None,
) -> FastAPI:
    """Build the FastAPI app wired to an ``IncidentService``.

    Provide exactly one of ``service`` or ``conn``. When neither is given, a
    connection is bootstrapped from configuration (the production default).
    Tests pass a fresh in-memory connection or a pre-built service to isolate
    state.
    """
    if service is not None and conn is not None:
        raise ValueError("Pass either 'service' or 'conn', not both.")
    if service is None:
        connection = conn if conn is not None else db.bootstrap()
        service = IncidentService(connection)

    app = FastAPI(title="KiroOps incident-management")
    app.state.incident_service = service
    register_exception_handlers(app)

    def _provide_service() -> IncidentService:
        return app.state.incident_service

    # Bind the module-level dependency symbol to this app's service so routes
    # depending on ``get_service`` resolve correctly (and stay overridable).
    app.dependency_overrides[get_service] = _provide_service

    @app.post(
        "/incidents",
        status_code=status.HTTP_201_CREATED,
        response_model=IncidentResponse,
    )
    def create_incident(
        body: CreateIncidentRequest,
        svc: IncidentService = Depends(get_service),
    ) -> IncidentResponse:
        """Create an incident (Req 1.1). Returns 201 with the created incident."""
        incident = svc.create(body.title, body.severity, body.service)
        return IncidentResponse.from_incident(incident)

    @app.get("/incidents", response_model=list[IncidentSummary])
    def list_incidents(
        svc: IncidentService = Depends(get_service),
    ) -> list[IncidentSummary]:
        """List all incidents as summaries (Req 2.1)."""
        return [IncidentSummary.from_incident(i) for i in svc.list()]

    @app.get(
        "/incidents/{incident_id}",
        response_model=IncidentDetailResponse,
    )
    def get_incident(
        incident_id: str,
        svc: IncidentService = Depends(get_service),
    ) -> IncidentDetailResponse:
        """Get one incident with its timeline (Req 2.2); 404 if unknown (Req 2.3)."""
        detail = svc.get(incident_id)
        return IncidentDetailResponse.from_detail(detail.incident, detail.timeline)

    @app.patch(
        "/incidents/{incident_id}/status",
        response_model=IncidentResponse,
    )
    def update_status(
        incident_id: str,
        body: UpdateStatusRequest,
        svc: IncidentService = Depends(get_service),
    ) -> IncidentResponse:
        """Advance an incident's status (Req 3.1).

        404 if the id is unknown (Req 2.3); 409 on an invalid/backward transition
        with the status preserved (Req 3.3, 7.4); 422 on an unknown status value
        (Req 3.4, enforced by the enum-typed request model).
        """
        incident = svc.update_status(incident_id, body.status)
        return IncidentResponse.from_incident(incident)

    return app
