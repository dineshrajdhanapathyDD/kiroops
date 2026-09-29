"""Thin wrapper exposing the service-metrics tool for the MCP server.

Delegates to ``backend.mcp.tools`` so the seeding logic is not duplicated.
"""

from __future__ import annotations

import _shared  # noqa: F401  (side effect: puts workspace root on sys.path)
from backend.mcp import tools


def get_service_metrics(service: str, window_minutes: int = 15) -> dict:
    """Return simulated service metrics for a service.

    See ``backend.mcp.tools.get_service_metrics`` for the output shape.
    """

    return tools.get_service_metrics(service, window_minutes)
