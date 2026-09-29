"""Unit tests for the MCP evidence-gathering tools (Task 9.3).

Validates the exact output shape (keys and types) documented in design.md for
each tool, that seeded data is coherent and repeatable within a session (same
service -> same data), and that value ranges/allowed sets hold. Also checks the
``SimulatedMcpClient`` delegates to the same tools.

Requirements: 4.1.
"""

from __future__ import annotations

from backend.mcp import tools
from backend.mcp.client import McpClient, SimulatedMcpClient
from backend.mcp.tools import LOG_LEVELS

_SERVICES = ["checkout", "payments", "search", "auth-gateway"]
_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# --------------------------------------------------------------------------- #
# get_recent_logs
# --------------------------------------------------------------------------- #
def test_get_recent_logs_shape_and_types() -> None:
    result = tools.get_recent_logs("checkout", limit=20)
    assert set(result.keys()) == {"service", "entries"}
    assert result["service"] == "checkout"
    assert isinstance(result["entries"], list)
    assert len(result["entries"]) == 20
    for entry in result["entries"]:
        assert set(entry.keys()) == {"timestamp", "level", "message"}
        assert isinstance(entry["timestamp"], str)
        assert entry["level"] in LOG_LEVELS
        assert isinstance(entry["message"], str)


def test_get_recent_logs_respects_limit() -> None:
    assert len(tools.get_recent_logs("checkout", limit=0)["entries"]) == 0
    assert len(tools.get_recent_logs("checkout", limit=5)["entries"]) == 5


def test_get_recent_logs_repeatable_for_same_service() -> None:
    assert tools.get_recent_logs("payments", limit=15) == tools.get_recent_logs(
        "payments", limit=15
    )


def test_get_recent_logs_levels_within_allowed_set() -> None:
    for service in _SERVICES:
        for entry in tools.get_recent_logs(service, limit=40)["entries"]:
            assert entry["level"] in set(LOG_LEVELS)


# --------------------------------------------------------------------------- #
# get_service_metrics
# --------------------------------------------------------------------------- #
def test_get_service_metrics_shape_and_types() -> None:
    result = tools.get_service_metrics("checkout")
    assert set(result.keys()) == {"service", "metrics"}
    assert result["service"] == "checkout"
    metrics = result["metrics"]
    assert set(metrics.keys()) == {
        "error_rate",
        "p95_latency_ms",
        "cpu_pct",
        "memory_pct",
    }
    for value in metrics.values():
        assert isinstance(value, float)


def test_get_service_metrics_value_ranges() -> None:
    for service in _SERVICES:
        metrics = tools.get_service_metrics(service)["metrics"]
        assert 0.0 <= metrics["error_rate"] <= 1.0
        assert metrics["p95_latency_ms"] >= 0.0
        assert 0.0 <= metrics["cpu_pct"] <= 100.0
        assert 0.0 <= metrics["memory_pct"] <= 100.0


def test_get_service_metrics_repeatable_for_same_service() -> None:
    assert tools.get_service_metrics("search") == tools.get_service_metrics("search")


def test_metrics_error_rate_tracks_log_error_volume() -> None:
    # Coherence: services with more ERROR log entries report a higher error_rate.
    def error_ratio(service: str) -> float:
        entries = tools.get_recent_logs(service, limit=200)["entries"]
        errors = sum(1 for e in entries if e["level"] == "ERROR")
        return errors / len(entries)

    samples = sorted(
        _SERVICES, key=lambda s: tools.get_service_metrics(s)["metrics"]["error_rate"]
    )
    lowest, highest = samples[0], samples[-1]
    # The service with the lowest reported error_rate should not have a higher
    # observed ERROR log ratio than the one with the highest reported error_rate.
    assert error_ratio(lowest) <= error_ratio(highest) + 0.15


# --------------------------------------------------------------------------- #
# get_incident_history
# --------------------------------------------------------------------------- #
def test_get_incident_history_shape_and_types() -> None:
    result = tools.get_incident_history("payments", limit=6)
    assert set(result.keys()) == {"service", "incidents"}
    assert result["service"] == "payments"
    assert isinstance(result["incidents"], list)
    assert len(result["incidents"]) == 6
    for incident in result["incidents"]:
        assert set(incident.keys()) == {
            "incident_id",
            "title",
            "severity",
            "resolved_at",
        }
        assert incident["incident_id"].startswith("INC-")
        assert isinstance(incident["title"], str)
        assert incident["severity"] in _SEVERITIES
        assert isinstance(incident["resolved_at"], str)


def test_get_incident_history_repeatable_for_same_service() -> None:
    assert tools.get_incident_history("auth-gateway") == tools.get_incident_history(
        "auth-gateway"
    )


# --------------------------------------------------------------------------- #
# search_runbook
# --------------------------------------------------------------------------- #
def test_search_runbook_shape_and_types() -> None:
    result = tools.search_runbook("checkout", "high error rate")
    assert set(result.keys()) == {"matches"}
    assert isinstance(result["matches"], list)
    assert len(result["matches"]) >= 1
    for match in result["matches"]:
        assert set(match.keys()) == {"runbook_id", "title", "excerpt", "score"}
        assert isinstance(match["runbook_id"], str)
        assert isinstance(match["title"], str)
        assert isinstance(match["excerpt"], str)
        assert isinstance(match["score"], float)


def test_search_runbook_scores_in_range_and_sorted_desc() -> None:
    matches = tools.search_runbook("payments", "latency")["matches"]
    for match in matches:
        assert 0.0 <= match["score"] <= 1.0
    scores = [m["score"] for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_search_runbook_repeatable_for_same_inputs() -> None:
    assert tools.search_runbook("search", "timeout") == tools.search_runbook(
        "search", "timeout"
    )


# --------------------------------------------------------------------------- #
# Different services generally produce different data (seeding is per-service)
# --------------------------------------------------------------------------- #
def test_distinct_services_have_distinct_metrics() -> None:
    a = tools.get_service_metrics("checkout")["metrics"]
    b = tools.get_service_metrics("payments")["metrics"]
    assert a != b


# --------------------------------------------------------------------------- #
# SimulatedMcpClient delegates to the same tools
# --------------------------------------------------------------------------- #
def test_simulated_client_satisfies_protocol_and_delegates() -> None:
    client = SimulatedMcpClient()
    assert isinstance(client, McpClient)
    assert client.get_recent_logs("checkout", 10) == tools.get_recent_logs(
        "checkout", 10
    )
    assert client.get_service_metrics("checkout") == tools.get_service_metrics(
        "checkout"
    )
    assert client.get_incident_history("checkout") == tools.get_incident_history(
        "checkout"
    )
    assert client.search_runbook("checkout", "q") == tools.search_runbook(
        "checkout", "q"
    )
