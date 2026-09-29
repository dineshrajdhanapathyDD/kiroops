"""Thin wrappers exposing incident-history and runbook-search tools.

Delegates to ``backend.mcp.tools`` so the seeding logic is not duplicated.
"""

from __future__ import annotations

import _shared  # noqa: F401  (side effect: puts workspace root on sys.path)
from backend.mcp import tools


def get_incident_history(service: str, limit: int = 10) -> dict:
    """Return simulated past resolved incidents for a service.

    See ``backend.mcp.tools.get_incident_history`` for the output shape.
    """

    return tools.get_incident_history(service, limit)


def search_runbook(service: str, query: str) -> dict:
    """Return simulated runbook matches for a service and free-text query.

    See ``backend.mcp.tools.search_runbook`` for the output shape.
    """

    return tools.search_runbook(service, query)
