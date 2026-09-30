"""DiagnosisService: orchestrate a diagnosis request end to end (Task 10.5).

The service is the deterministic entry point behind ``POST
/incidents/{id}/diagnosis``. It:

1. loads the incident (raises ``NotFoundError`` -> 404 if missing);
2. appends a "diagnosis requested" timeline event (Req 4.3);
3. invokes the :class:`~backend.agent.diagnosis_agent.DiagnosisAgent`;
4. on success, persists the ``Diagnosis`` and the derived ``RemediationAction``
   set, then appends an "actions suggested" timeline event (Req 4.4, 5.1, 5.2);
5. on a diagnosis-unavailable result, raises
   :class:`~backend.service.errors.DiagnosisUnavailableError` and leaves the
   incident status unchanged (Req 4.5).

Remediation ``action_id`` values are generated deterministically per incident as
``ACT-0001``, ``ACT-0002``, ... in derivation order. The LLM remains the only
non-deterministic step, isolated inside the agent.

Requirements: 4.3, 4.4, 4.5, 5.1, 5.2, 5.3.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from backend.agent.diagnosis_agent import DiagnosisAgent
from backend.agent.provider import (
    DiagnosisResult,
    DiagnosisUnavailable,
    RemediationSuggestion,
)
from dataclasses import dataclass

from backend.domain.models import (
    Diagnosis,
    Incident,
    RemediationAction,
    TimelineEventType,
)
from backend.repository.factory import RepositoryBundle, build_sqlite
from backend.service.errors import DiagnosisUnavailableError, NotFoundError


def _default_now() -> datetime:
    """Default clock: timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _action_id_for(seq: int) -> str:
    """Derive a deterministic remediation action id (``ACT-####``)."""
    return "ACT-" + str(seq).zfill(4)


@dataclass(frozen=True)
class DiagnosisOutcome:
    """The persisted result of a successful diagnosis, for the API layer.

    Carries the summary and evidence references from the diagnosis plus the
    remediation actions as persisted (with their assigned ``action_id`` values),
    so the ``POST`` response and the later ``GET`` return identical ids.
    """

    incident_id: str
    summary: str
    evidence_refs: list[str]
    remediation_actions: list[RemediationAction]


class DiagnosisService:
    """Persist-and-orchestrate wrapper around the ``DiagnosisAgent`` (Req 4, 5)."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        agent: DiagnosisAgent | None = None,
        now: Callable[[], datetime] = _default_now,
        *,
        repositories: RepositoryBundle | None = None,
    ) -> None:
        """Compose the service over a repository bundle.

        Backwards-compatible: the original ``(conn, agent, now)`` call builds the
        SQLite bundle, so existing callers and tests keep working unchanged.
        Alternatively pass a ready ``repositories`` bundle from
        :mod:`backend.repository.factory` to run over any backend (e.g. DynamoDB)
        without the service knowing which one. ``agent`` is still required.
        """
        if agent is None:
            raise ValueError("DiagnosisService requires a DiagnosisAgent.")
        bundle = self._resolve_bundle(conn, repositories)
        self._incidents = bundle.incidents
        self._timeline = bundle.timeline
        self._diagnoses = bundle.diagnoses
        self._remediations = bundle.remediations
        self._agent = agent
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
            "DiagnosisService requires either a sqlite3.Connection or a "
            "repositories bundle."
        )

    @classmethod
    def from_repositories(
        cls,
        repositories: RepositoryBundle,
        agent: DiagnosisAgent,
        now: Callable[[], datetime] = _default_now,
    ) -> "DiagnosisService":
        """Build a service over an explicit repository bundle (any backend)."""
        return cls(agent=agent, now=now, repositories=repositories)

    def diagnose(self, incident_id: str) -> DiagnosisOutcome:
        """Run a diagnosis for an incident and persist the outcome.

        Raises ``NotFoundError`` if the incident is unknown (Req 2.3), and
        ``DiagnosisUnavailableError`` if the LLM is unavailable, leaving the
        incident status unchanged (Req 4.5). On success returns a
        :class:`DiagnosisOutcome` (with persisted action ids) for the API layer
        to serialize.
        """
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError(incident_id)

        # Req 4.3: record that a diagnosis was requested before invoking the LLM.
        self._timeline.append(
            incident_id,
            TimelineEventType.DIAGNOSIS_REQUESTED,
            self._now(),
            {},
        )

        outcome = self._agent.diagnose(incident)
        if isinstance(outcome, DiagnosisUnavailable):
            # Req 4.5: no diagnosis produced; status is left unchanged.
            raise DiagnosisUnavailableError(incident_id)

        return self._persist_success(incident, outcome)

    def list_remediation_actions(self, incident_id: str) -> list[RemediationAction]:
        """Return the remediation actions for an incident (Req 5.3).

        Raises ``NotFoundError`` if the incident is unknown (Req 2.3).
        """
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError(incident_id)
        return self._remediations.list(incident_id)

    def _persist_success(
        self, incident: Incident, result: DiagnosisResult
    ) -> DiagnosisOutcome:
        """Persist the diagnosis and derived actions, then record the event.

        Persists the ``Diagnosis`` (Req 4.4) and the ``RemediationAction`` set
        with deterministic ids (Req 5.1), then appends an "actions suggested"
        timeline event (Req 5.2). Returns the outcome carrying the persisted
        actions (with their assigned ids).
        """
        created_at = self._now()
        self._diagnoses.save(
            Diagnosis(
                incident_id=incident.incident_id,
                summary=result.summary,
                evidence_refs=list(result.evidence_refs),
                created_at=created_at,
            )
        )
        actions = self._to_actions(incident.incident_id, result.remediation_actions)
        self._remediations.save_all(actions)
        self._timeline.append(
            incident.incident_id,
            TimelineEventType.ACTIONS_SUGGESTED,
            self._now(),
            {"action_ids": [a.action_id for a in actions]},
        )
        return DiagnosisOutcome(
            incident_id=incident.incident_id,
            summary=result.summary,
            evidence_refs=list(result.evidence_refs),
            remediation_actions=actions,
        )

    def _to_actions(
        self, incident_id: str, suggestions: list[RemediationSuggestion]
    ) -> list[RemediationAction]:
        """Turn agent suggestions into persistable actions with stable ids."""
        return [
            RemediationAction(
                action_id=_action_id_for(index),
                incident_id=incident_id,
                description=suggestion.description,
                rationale=suggestion.rationale,
            )
            for index, suggestion in enumerate(suggestions, start=1)
        ]
