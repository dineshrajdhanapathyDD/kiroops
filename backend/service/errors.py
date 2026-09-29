"""Typed domain errors for the service layer.

These are raised by the service layer to signal business-rule violations. They
carry no HTTP awareness: the API layer (a later task) is solely responsible for
mapping them onto the shared error envelope and status codes. Keeping them here,
rather than in the API layer, lets the service enforce the rules while remaining
framework-agnostic (no FastAPI import), per the architecture steering.

Requirements: 1.6, 1.7, 2.3, 3.3, 3.4, 7.4.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for all service-layer domain errors."""


class ValidationError(ServiceError):
    """A request field failed validation (Req 1.6, 1.7).

    ``field`` names the offending field (e.g. ``"title"`` or ``"severity"``) so
    the API layer can surface it in the error envelope's ``field`` slot.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class NotFoundError(ServiceError):
    """A referenced entity does not exist (Req 2.3).

    ``incident_id`` records which id was not found.
    """

    def __init__(self, incident_id: str) -> None:
        message = f"Incident '{incident_id}' was not found."
        super().__init__(message)
        self.incident_id = incident_id
        self.message = message


class InvalidTransitionError(ServiceError):
    """A requested status change is not a Valid_Transition (Req 3.3, 7.4).

    Carries the current and requested target status. When this is raised the
    service performs no write, so the stored status is preserved.
    """

    def __init__(self, current: str, target: str) -> None:
        message = f"Cannot transition status from {current} to {target}."
        super().__init__(message)
        self.current = current
        self.target = target
        self.message = message


class DiagnosisUnavailableError(ServiceError):
    """The LLM_Provider was unavailable during a diagnosis request (Req 4.5).

    Raised by the ``DiagnosisService`` when the agent returns a
    diagnosis-unavailable result. When this is raised no diagnosis is persisted
    and the incident status is left unchanged; the API layer maps it to 503.
    """

    def __init__(self, incident_id: str) -> None:
        message = (
            f"Diagnosis for incident '{incident_id}' is unavailable: "
            "the LLM provider could not be reached."
        )
        super().__init__(message)
        self.incident_id = incident_id
        self.message = message
