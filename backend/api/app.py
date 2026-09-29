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

from backend.agent.default_provider import build_default_provider
from backend.agent.diagnosis_agent import DiagnosisAgent
from backend.agent.provider import LlmProvider
from backend.api.errors import register_exception_handlers
from backend.api.models import (
    CreateIncidentRequest,
    DiagnosisResponse,
    IncidentDetailResponse,
    IncidentResponse,
    IncidentSummary,
    RemediationActionModel,
    UpdateStatusRequest,
)
from backend.mcp.client import SimulatedMcpClient
from backend.repository import db
from backend.service.diagnosis_service import DiagnosisService
from backend.service.incident_service import IncidentService


def get_service() -> IncidentService:
    """Dependency placeholder; replaced per-app by ``create_app``.

    The real provider is bound in ``create_app`` so the service (and its
    connection) is created once and shared. Declaring it here gives routes a
    stable dependency symbol that can also be overridden in tests via
    ``app.dependency_overrides[get_service]``.
    """
    raise RuntimeError("IncidentService dependency is not configured.")


def get_diagnosis_service() -> DiagnosisService:
    """Dependency placeholder for the diagnosis service; bound in ``create_app``."""
    raise RuntimeError("DiagnosisService dependency is not configured.")


def create_app(
    service: IncidentService | None = None,
    conn: sqlite3.Connection | None = None,
    llm: LlmProvider | None = None,
    diagnosis_service: DiagnosisService | None = None,
) -> FastAPI:
    """Build the FastAPI app wired to the incident and diagnosis services.

    Provide at most one of ``service`` or ``conn``; when neither is given a
    connection is bootstrapped from configuration (the production default). The
    same connection backs both the ``IncidentService`` and the
    ``DiagnosisService`` so they share one database.

    The LLM boundary is injectable (per the architecture steering): pass a stub
    ``llm`` (tests) or a full ``diagnosis_service`` to control the agent. When
    neither is given, the default provider is built from ``LlmConfig`` and is
    always-unavailable, so out of the box a diagnosis request returns 503 with
    the incident status unchanged (Req 4.5) until the real provider (Task 12)
    is wired in.

    Note: when a pre-built ``service`` is passed without ``conn`` or an explicit
    ``diagnosis_service``, its connection is reused to build the diagnosis
    service so both services stay on the same database.
    """
    if service is not None and conn is not None:
        raise ValueError("Pass either 'service' or 'conn', not both.")

    connection: sqlite3.Connection
    if service is None:
        connection = conn if conn is not None else db.bootstrap()
        service = IncidentService(connection)
    else:
        # Reuse the pre-built service's connection so the diagnosis service
        # (built below when not injected) shares the same database.
        connection = service._incidents._conn  # noqa: SLF001 (intentional reuse)

    if diagnosis_service is None:
        provider = llm if llm is not None else build_default_provider()
        agent = DiagnosisAgent(SimulatedMcpClient(), provider)
        diagnosis_service = DiagnosisService(connection, agent)

    app = FastAPI(title="KiroOps incident-management")
    app.state.incident_service = service
    app.state.diagnosis_service = diagnosis_service
    register_exception_handlers(app)

    def _provide_service() -> IncidentService:
        return app.state.incident_service

    def _provide_diagnosis_service() -> DiagnosisService:
        return app.state.diagnosis_service

    # Bind the module-level dependency symbols to this app's services so routes
    # depending on them resolve correctly (and stay overridable).
    app.dependency_overrides[get_service] = _provide_service
    app.dependency_overrides[get_diagnosis_service] = _provide_diagnosis_service

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

    @app.post(
        "/incidents/{incident_id}/diagnosis",
        response_model=DiagnosisResponse,
    )
    def request_diagnosis(
        incident_id: str,
        svc: DiagnosisService = Depends(get_diagnosis_service),
    ) -> DiagnosisResponse:
        """Request an AI diagnosis for an incident (Req 4).

        404 if the id is unknown (Req 2.3); 503 diagnosis-unavailable when the
        LLM provider fails, with the incident status left unchanged (Req 4.5).
        On success returns the diagnosis summary, evidence references, and the
        derived remediation actions (Req 4.2, 5.1).
        """
        result = svc.diagnose(incident_id)
        return DiagnosisResponse(
            incident_id=result.incident_id,
            summary=result.summary,
            evidence_refs=list(result.evidence_refs),
            remediation_actions=[
                RemediationActionModel(
                    action_id=action.action_id,
                    description=action.description,
                    rationale=action.rationale,
                )
                for action in result.remediation_actions
            ],
        )

    @app.get(
        "/incidents/{incident_id}/remediation-actions",
        response_model=list[RemediationActionModel],
    )
    def get_remediation_actions(
        incident_id: str,
        svc: DiagnosisService = Depends(get_diagnosis_service),
    ) -> list[RemediationActionModel]:
        """Return the remediation actions for an incident (Req 5.3).

        404 if the incident id is unknown (Req 2.3).
        """
        actions = svc.list_remediation_actions(incident_id)
        return [
            RemediationActionModel(
                action_id=a.action_id,
                description=a.description,
                rationale=a.rationale,
            )
            for a in actions
        ]

    return app
