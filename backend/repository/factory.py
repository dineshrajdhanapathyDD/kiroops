"""Repository factory: build the four repositories for a chosen backend (Phase 1).

The service layer obtains its repositories from here instead of constructing
them directly, so it does not need to know whether persistence is SQLite or
DynamoDB. The four repository interfaces are described structurally with
``Protocol`` classes (matching the existing SQLite repositories' public
methods), and a ``RepositoryBundle`` groups one concrete instance of each.

Only :func:`build_dynamodb` imports the DynamoDB modules (and therefore boto3);
:func:`build_sqlite` and the default path never do, so the SQLite backend keeps
running without boto3 installed.

Requirements: storage-boundary composition (mirrors SQLite + DynamoDB repos).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from backend.config import (
    PERSISTENCE_DYNAMODB,
    PERSISTENCE_SQLITE,
    DynamoConfig,
    get_persistence,
)
from backend.domain.models import (
    Diagnosis,
    Incident,
    IncidentStatus,
    RemediationAction,
    Severity,
    TimelineEvent,
    TimelineEventType,
)


class IncidentRepositoryProtocol(Protocol):
    """Structural interface implemented by both incident repositories."""

    def create(
        self, title: str, severity: Severity, service: str, created_at: datetime
    ) -> Incident: ...

    def get(self, incident_id: str) -> Incident | None: ...

    def list(self) -> list[Incident]: ...

    def update_status(self, incident_id: str, new_status: IncidentStatus) -> None: ...


class TimelineRepositoryProtocol(Protocol):
    """Structural interface implemented by both timeline repositories."""

    def append(
        self,
        incident_id: str,
        type: TimelineEventType,
        timestamp: datetime,
        details: dict,
    ) -> None: ...

    def list(self, incident_id: str) -> list[TimelineEvent]: ...


class DiagnosisRepositoryProtocol(Protocol):
    """Structural interface implemented by both diagnosis repositories."""

    def save(self, diagnosis: Diagnosis) -> None: ...

    def get(self, incident_id: str) -> Diagnosis | None: ...


class RemediationRepositoryProtocol(Protocol):
    """Structural interface implemented by both remediation repositories."""

    def save_all(self, actions: Iterable[RemediationAction]) -> None: ...

    def list(self, incident_id: str) -> list[RemediationAction]: ...


@dataclass(frozen=True)
class RepositoryBundle:
    """One concrete instance of each repository, for the selected backend."""

    incidents: IncidentRepositoryProtocol
    timeline: TimelineRepositoryProtocol
    diagnoses: DiagnosisRepositoryProtocol
    remediations: RemediationRepositoryProtocol


def build_sqlite(conn: sqlite3.Connection) -> RepositoryBundle:
    """Build the SQLite-backed repository bundle from a connection."""
    from backend.repository.diagnosis_repository import DiagnosisRepository
    from backend.repository.incident_repository import IncidentRepository
    from backend.repository.remediation_repository import RemediationRepository
    from backend.repository.timeline_repository import TimelineRepository

    return RepositoryBundle(
        incidents=IncidentRepository(conn),
        timeline=TimelineRepository(conn),
        diagnoses=DiagnosisRepository(conn),
        remediations=RemediationRepository(conn),
    )


def build_dynamodb(table: Any) -> RepositoryBundle:
    """Build the DynamoDB-backed repository bundle from a boto3 ``Table``.

    Imports the DynamoDB repositories lazily so boto3 is only required when this
    backend is actually selected.
    """
    from backend.repository.dynamo_diagnosis_repository import (
        DynamoDiagnosisRepository,
    )
    from backend.repository.dynamo_incident_repository import (
        DynamoIncidentRepository,
    )
    from backend.repository.dynamo_remediation_repository import (
        DynamoRemediationRepository,
    )
    from backend.repository.dynamo_timeline_repository import (
        DynamoTimelineRepository,
    )

    return RepositoryBundle(
        incidents=DynamoIncidentRepository(table),
        timeline=DynamoTimelineRepository(table),
        diagnoses=DynamoDiagnosisRepository(table),
        remediations=DynamoRemediationRepository(table),
    )


def build_from_config(
    conn: sqlite3.Connection | None = None,
    env: dict[str, str] | None = None,
) -> RepositoryBundle:
    """Build the repository bundle for the configured persistence backend.

    - ``sqlite`` (default): requires ``conn`` (a bootstrapped connection).
    - ``dynamodb``: reads table name + region from :class:`DynamoConfig` and
      resolves the ``Table`` via :mod:`backend.repository.dynamo`.
    """
    backend = get_persistence(env)
    if backend == PERSISTENCE_SQLITE:
        if conn is None:
            raise ValueError("SQLite persistence requires a sqlite3.Connection.")
        return build_sqlite(conn)
    if backend == PERSISTENCE_DYNAMODB:
        from backend.repository import dynamo

        cfg = DynamoConfig.from_env(env)
        table = dynamo.get_table(cfg.table_name, cfg.region)
        return build_dynamodb(table)
    # get_persistence already validates; this is defensive.
    raise ValueError(f"Unsupported persistence backend: {backend!r}")
