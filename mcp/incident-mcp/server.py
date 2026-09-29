"""Standalone incident-mcp server (Kiro University Lesson 6).

Exposes the four KiroOps evidence-gathering tools over the Model Context
Protocol using the official Python MCP SDK (``FastMCP``). All data is simulated
and seeded per service (see ``backend/mcp/tools.py``, the single source of
truth); this server holds only thin wrappers that call that logic.

Run it directly::

    python server.py          # stdio transport (what Kiro launches)
    mcp run server.py         # via the mcp CLI, if installed

The ``mcp`` SDK is imported lazily inside ``main`` so the module stays
importable even where the SDK is not installed (the backend test-suite never
starts this server).
"""

from __future__ import annotations

import _shared  # noqa: F401  (side effect: puts workspace root on sys.path)
from tools.incidents import get_incident_history, search_runbook
from tools.logs import get_recent_logs
from tools.metrics import get_service_metrics


def build_server():
    """Construct and return a FastMCP server with the four tools registered.

    Imports the MCP SDK here (not at module import time) so this file remains
    importable without the SDK installed.
    """

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("incident-mcp")

    @server.tool(name="get_recent_logs")
    def recent_logs(service: str, limit: int = 50) -> dict:
        """Recent simulated log entries (INFO/WARN/ERROR) for a service."""
        return get_recent_logs(service, limit)

    @server.tool(name="get_service_metrics")
    def service_metrics(service: str, window_minutes: int = 15) -> dict:
        """Simulated service metrics: error_rate, p95_latency_ms, cpu, memory."""
        return get_service_metrics(service, window_minutes)

    @server.tool(name="get_incident_history")
    def incident_history(service: str, limit: int = 10) -> dict:
        """Simulated history of previously resolved incidents for a service."""
        return get_incident_history(service, limit)

    @server.tool(name="search_runbook")
    def runbook_search(service: str, query: str) -> dict:
        """Search simulated runbooks for a service; returns scored matches."""
        return search_runbook(service, query)

    return server


def main() -> None:
    """Entry point: build the server and serve over stdio."""

    build_server().run()


if __name__ == "__main__":
    main()
