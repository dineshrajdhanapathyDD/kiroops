"""Domain enums and dataclasses (Task 2.1).

Closed sets are modeled as ``(str, Enum)`` so their values serialize directly to
their string form and compare equal to the underlying string. Domain objects are
plain dataclasses, per the coding-standards steering. The enum string values and
dataclass fields match ``design.md`` exactly.

Requirements: 1.2, 1.4, 6.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    """Impact level supplied at incident creation (Req 1.7)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    """Lifecycle state of an incident (Req 3)."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class TimelineEventType(str, Enum):
    """The recorded kinds of timeline event (Req 6.1).

    The string values are the human-readable event names from ``design.md`` and
    must not change: they are persisted and surfaced verbatim in the timeline.
    """

    CREATED = "created"
    STATUS_CHANGED = "status changed"
    DIAGNOSIS_REQUESTED = "diagnosis requested"
    ACTIONS_SUGGESTED = "actions suggested"


@dataclass
class Incident:
    """An operational incident record (Req 1.2, 1.4, 7.1)."""

    incident_id: str
    title: str
    severity: Severity
    service: str
    status: IncidentStatus
    created_at: datetime


@dataclass
class TimelineEvent:
    """A single append-only entry in an incident timeline (Req 6.1)."""

    incident_id: str
    seq: int
    type: TimelineEventType
    timestamp: datetime
    details: dict


@dataclass
class Diagnosis:
    """An evidence-based analysis produced for an incident (Req 4.2, 4.4)."""

    incident_id: str
    summary: str
    evidence_refs: list[str]
    created_at: datetime


@dataclass
class RemediationAction:
    """A recommended corrective step derived from a diagnosis (Req 5.1)."""

    action_id: str
    incident_id: str
    description: str
    rationale: str
