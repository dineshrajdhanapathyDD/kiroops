"""McpClient interface used by the Diagnosis_Agent (Task 9.2).

The Diagnosis_Agent depends on a stable client contract rather than the tool
functions directly, so it can be exercised against a stub in tests. This module
defines the ``McpClient`` Protocol and a concrete ``SimulatedMcpClient`` that
wraps the seeded tools from :mod:`backend.mcp.tools`.

Kept dependency-free (pure Python, no MCP SDK) so backend tests need nothing
extra installed. Importable as ``backend.mcp.client``.

Requirements: 4.1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.mcp import tools
from backend.mcp.tools import (
    IncidentHistory,
    RecentLogs,
    RunbookSearch,
    ServiceMetrics,
)


@runtime_checkable
class McpClient(Protocol):
    """Stable contract over the four MCP evidence-gathering tools.

    The Diagnosis_Agent depends only on this Protocol, so any implementation
    (the simulated client below, or a test stub) can be injected.
    """

    def get_recent_logs(self, service: str, limit: int = 50) -> RecentLogs: ...

    def get_service_metrics(
        self, service: str, window_minutes: int = 15
    ) -> ServiceMetrics: ...

    def get_incident_history(
        self, service: str, limit: int = 10
    ) -> IncidentHistory: ...

    def search_runbook(self, service: str, query: str) -> RunbookSearch: ...


class SimulatedMcpClient:
    """Concrete :class:`McpClient` backed by the seeded simulated tools.

    Thin delegation to :mod:`backend.mcp.tools` so the seeding logic has a
    single source of truth and is never duplicated.
    """

    def get_recent_logs(self, service: str, limit: int = 50) -> RecentLogs:
        return tools.get_recent_logs(service, limit)

    def get_service_metrics(
        self, service: str, window_minutes: int = 15
    ) -> ServiceMetrics:
        return tools.get_service_metrics(service, window_minutes)

    def get_incident_history(
        self, service: str, limit: int = 10
    ) -> IncidentHistory:
        return tools.get_incident_history(service, limit)

    def search_runbook(self, service: str, query: str) -> RunbookSearch:
        return tools.search_runbook(service, query)
