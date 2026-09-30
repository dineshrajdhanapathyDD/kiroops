"""IncidentService: deterministic incident business rules (Tasks 6.1, 6.3).

All incident business rules live here, not in the repositories: title/severity
validation, initial-state assignment, the timeline-append policy, and status
transition validation via the pure ``is_valid_transition`` state machine. The
service composes ``IncidentRepository`` and ``TimelineRepository`` over a single
shared ``sqlite3.Connection``.

The clock is injected (``now``) so the timestamps written on "created" and
"status changed" events are deterministic in tests. It defaults to
``datetime.now(timezone.utc)``.

Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 7.4.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.domain.models import (
    Incident,
    IncidentStatus,
    Severity,
    TimelineEvent,
    TimelineEventType,
)
from backend.domain.status_machine import is_valid_transition
from backend.repository.factory import RepositoryBundle, build_sqlite
from backend.service.errors import (
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)


@dataclass
class IncidentDetail:
    """An incident together with its full timeline (Req 2.2).

    Returned by ``IncidentService.get`` as a serialization-friendly structure the
    API layer can turn into an ``IncidentDetailResponse``. The timeline is
    ordered earliest -> latest (the repository guarantees the ordering).
    """

    incident: Incident
    timeline: list[TimelineEvent]


def _default_now() -> datetime:
    """Default clock: timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class IncidentService:
    """Create, list, read, and advance incidents (Req 1, 2, 3)."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        now: Callable[[], datetime] = _default_now,
        *,
        repositories: RepositoryBundle | None = None,
    ) -> None:
        """Compose the service over a repository bundle.

        Backwards-compatible: passing a ``sqlite3.Connection`` (the original
        signature) builds the SQLite bundle, so existing callers and tests keep
        working unchanged. Alternatively pass a ready ``repositories`` bundle
        from :mod:`backend.repository.factory` to run over any backend
        (e.g. DynamoDB) without the service knowing which one.
        """
        bundle = self._resolve_bundle(conn, repositories)
        self._incidents = bundle.incidents
        self._timeline = bundle.timeline
        self._now = now

    @staticmethod
    def _resolve_bundle(
        conn: sqlite3.Connection | None, repositories: RepositoryBundle | None
    ) -> RepositoryBundle:
        if repositories is not None:
            return repositories
        if conn is not None:
            return build_sqlite(conn)
        raise ValueError(
            "IncidentService requires either a sqlite3.Connection or a "
            "repositories bundle."
        )

    @classmethod
    def from_repositories(
        cls,
        repositories: RepositoryBundle,
        now: Callable[[], datetime] = _default_now,
    ) -> "IncidentService":
        """Build a service over an explicit repository bundle (any backend)."""
        return cls(now=now, repositories=repositories)

    def create(self, title: str, severity: Severity, service: str) -> Incident:
        """Validate, persist, and record the creation of a new incident.

        Rejects an empty or whitespace-only title (Req 1.6) and a severity that
        is not a valid ``Severity`` member (Req 1.7). On success the incident is
        persisted with status OPEN via the repository (Req 1.1, 1.4) and a
        "created" timeline event bearing the creation timestamp is appended
        (Req 1.5). A single clock reading is used for the timestamp.
        """
        if title is None or not title.strip():
            raise ValidationError("title", "Title must not be empty or whitespace.")
        if not isinstance(severity, Severity):
            raise ValidationError(
                "severity",
                "Severity must be one of LOW, MEDIUM, HIGH, or CRITICAL.",
            )

        created_at = self._now()
        incident = self._incidents.create(title, severity, service, created_at)
        self._timeline.append(
            incident.incident_id,
            TimelineEventType.CREATED,
            created_at,
            {"title": title, "severity": severity.value, "service": service},
        )
        return incident

    def list(self) -> list[Incident]:
        """Return all persisted incidents (Req 2.1)."""
        return self._incidents.list()

    def get(self, incident_id: str) -> IncidentDetail:
        """Return an incident with its timeline, or raise if unknown (Req 2.2, 2.3).

        Raises ``NotFoundError`` when no incident has the given id (Req 2.3).
        """
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError(incident_id)
        timeline = self._timeline.list(incident_id)
        return IncidentDetail(incident=incident, timeline=timeline)

    def update_status(
        self, incident_id: str, target: IncidentStatus
    ) -> Incident:
        """Advance an incident's status through a Valid_Transition (Req 3).

        Loads the incident (``NotFoundError`` if missing) and consults the pure
        ``is_valid_transition`` state machine. On a valid transition the new
        status is persisted and a "status changed" event recording the previous
        and new status is appended (Req 3.1, 3.2). On an invalid transition the
        method raises ``InvalidTransitionError`` and performs no write, so the
        stored status is preserved (Req 3.3, 7.4).
        """
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError(incident_id)

        current = incident.status
        if not is_valid_transition(current, target):
            raise InvalidTransitionError(current.value, target.value)

        self._incidents.update_status(incident_id, target)
        self._timeline.append(
            incident_id,
            TimelineEventType.STATUS_CHANGED,
            self._now(),
            {"from": current.value, "to": target.value},
        )
        return Incident(
            incident_id=incident.incident_id,
            title=incident.title,
            severity=incident.severity,
            service=incident.service,
            status=target,
            created_at=incident.created_at,
        )
