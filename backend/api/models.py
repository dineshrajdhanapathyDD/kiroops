"""API request/response models (Task 7.1).

Pydantic v2 models for the incident-management HTTP boundary. These mirror the
response shapes in ``design.md`` and are the only place request bodies are
shape-validated; all business rules stay in the service layer. Domain enums
(``Severity``, ``IncidentStatus``, ``TimelineEventType``) are reused directly so
an unknown enum value in a request body yields a 422 before any service call.

Requirements: 1.1, 2.1, 2.2, 3.1, 4.2, 5.1, 5.3.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.domain.models import (
    Incident,
    IncidentStatus,
    Severity,
    TimelineEvent,
    TimelineEventType,
)


def _iso(value: datetime) -> str:
    """Serialize a datetime to an ISO-8601 string."""
    return value.isoformat()


class CreateIncidentRequest(BaseModel):
    """Body for ``POST /incidents`` (Req 1.1).

    ``severity`` is typed as the ``Severity`` enum so an unrecognized value is
    rejected as a 422 request-shape error before the service is called (Req 1.7).
    The non-empty/whitespace title rule (Req 1.6) is enforced by the service so
    the failure carries the shared error envelope naming the field.
    """

    title: str
    severity: Severity
    service: str


class IncidentResponse(BaseModel):
    """Serialized incident returned by create, get, and status update."""

    incident_id: str
    title: str
    severity: Severity
    service: str
    status: IncidentStatus
    created_at: str  # ISO-8601

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentResponse":
        """Build the response from a domain ``Incident``."""
        return cls(
            incident_id=incident.incident_id,
            title=incident.title,
            severity=incident.severity,
            service=incident.service,
            status=incident.status,
            created_at=_iso(incident.created_at),
        )


class IncidentSummary(BaseModel):
    """Row shape for ``GET /incidents`` (Req 2.1)."""

    incident_id: str
    title: str
    severity: Severity
    service: str
    status: IncidentStatus

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentSummary":
        """Build the summary from a domain ``Incident``."""
        return cls(
            incident_id=incident.incident_id,
            title=incident.title,
            severity=incident.severity,
            service=incident.service,
            status=incident.status,
        )


class TimelineEventModel(BaseModel):
    """A single serialized timeline event (Req 6.1, 6.3)."""

    type: TimelineEventType
    timestamp: str  # ISO-8601
    details: dict

    @classmethod
    def from_event(cls, event: TimelineEvent) -> "TimelineEventModel":
        """Build the model from a domain ``TimelineEvent``."""
        return cls(
            type=event.type,
            timestamp=_iso(event.timestamp),
            details=event.details,
        )


class IncidentDetailResponse(IncidentResponse):
    """``IncidentResponse`` plus the full timeline (Req 2.2, 6.3).

    The timeline is ordered earliest -> latest by the repository/service.
    """

    timeline: list[TimelineEventModel]

    @classmethod
    def from_detail(
        cls, incident: Incident, timeline: list[TimelineEvent]
    ) -> "IncidentDetailResponse":
        """Build the detail response from an incident and its timeline."""
        return cls(
            incident_id=incident.incident_id,
            title=incident.title,
            severity=incident.severity,
            service=incident.service,
            status=incident.status,
            created_at=_iso(incident.created_at),
            timeline=[TimelineEventModel.from_event(e) for e in timeline],
        )


class UpdateStatusRequest(BaseModel):
    """Body for ``PATCH /incidents/{incident_id}/status`` (Req 3.1).

    ``status`` is typed as ``IncidentStatus`` so an unknown status value is a
    422 request-shape error and no state change occurs (Req 3.4).
    """

    status: IncidentStatus


class RemediationActionModel(BaseModel):
    """A recommended corrective step (Req 5.1, 5.3).

    Diagnosis endpoints are a later task; the model is defined now per Task 7.1.
    """

    action_id: str
    description: str
    rationale: str


class DiagnosisResponse(BaseModel):
    """Response for ``POST /incidents/{incident_id}/diagnosis`` (Req 4.2, 5.1).

    Diagnosis endpoints are a later task; the model is defined now per Task 7.1.
    """

    model_config = ConfigDict(protected_namespaces=())

    incident_id: str
    summary: str
    evidence_refs: list[str]
    remediation_actions: list[RemediationActionModel]
