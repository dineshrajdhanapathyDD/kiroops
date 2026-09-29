"""Thin wrapper exposing the recent-logs tool for the MCP server.

Delegates to ``backend.mcp.tools`` so the seeding logic is not duplicated.
"""

from __future__ import annotations

import _shared  # noqa: F401  (side effect: puts workspace root on sys.path)
from backend.mcp import tools


def get_recent_logs(service: str, limit: int = 50) -> dict:
    """Return simulated recent log entries for a service.

    See ``backend.mcp.tools.get_recent_logs`` for the output shape.
    """

    return tools.get_recent_logs(service, limit)
