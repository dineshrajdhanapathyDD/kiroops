"""MCP evidence-gathering tools with seeded simulated data (Task 9.1).

These four pure-Python functions return the exact output shapes documented in
``design.md`` (the MCP_Server table). They are dependency-free: no external
systems and no MCP SDK import, so the backend test-suite can exercise them
without installing anything extra.

Data is generated deterministically from a per-service seed derived from a
stable hash of the service name. Repeated calls for the same service within a
process therefore return coherent, repeatable data: for example, the reported
``error_rate`` in ``get_service_metrics`` tracks the volume of ERROR-level
entries produced by ``get_recent_logs`` for that same service.

Requirements: 4.1.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

LogLevel = Literal["INFO", "WARN", "ERROR"]

# Allowed log levels, exposed for tests and callers that validate the contract.
LOG_LEVELS: tuple[LogLevel, ...] = ("INFO", "WARN", "ERROR")


class LogEntry(TypedDict):
    timestamp: str
    level: LogLevel
    message: str


class RecentLogs(TypedDict):
    service: str
    entries: list[LogEntry]


class ServiceMetricValues(TypedDict):
    error_rate: float
    p95_latency_ms: float
    cpu_pct: float
    memory_pct: float


class ServiceMetrics(TypedDict):
    service: str
    metrics: ServiceMetricValues


class HistoricIncident(TypedDict):
    incident_id: str
    title: str
    severity: str
    resolved_at: str


class IncidentHistory(TypedDict):
    service: str
    incidents: list[HistoricIncident]


class RunbookMatch(TypedDict):
    runbook_id: str
    title: str
    excerpt: str
    score: float


class RunbookSearch(TypedDict):
    matches: list[RunbookMatch]


# Fixed reference instant for simulated timestamps. Using a constant (rather
# than wall-clock ``now``) keeps generated data byte-for-byte repeatable for a
# given service within and across sessions, which the tests and the design's
# "coherent, repeatable" contract require.
_REFERENCE_TIME = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_SEVERITIES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Message templates keyed by level so simulated logs read plausibly.
_LOG_MESSAGES: dict[LogLevel, tuple[str, ...]] = {
    "INFO": (
        "request completed",
        "health check ok",
        "cache warmed",
        "config reloaded",
        "connection established",
    ),
    "WARN": (
        "elevated latency observed",
        "retrying downstream call",
        "connection pool near capacity",
        "slow query detected",
        "circuit breaker half-open",
    ),
    "ERROR": (
        "unhandled exception",
        "downstream timeout",
        "connection pool exhausted",
        "database connection refused",
        "5xx returned to client",
    ),
}

_RUNBOOK_TITLES: tuple[str, ...] = (
    "Mitigating high error rate",
    "Scaling under CPU pressure",
    "Recovering from database connection exhaustion",
    "Investigating latency spikes",
    "Handling memory pressure and OOM",
    "Rolling back a bad deploy",
)

_RUNBOOK_EXCERPTS: tuple[str, ...] = (
    "Check recent deploys and roll back if error rate exceeds threshold.",
    "Scale the service horizontally and inspect CPU-bound hot paths.",
    "Increase the connection pool size and verify downstream health.",
    "Correlate p95 latency with downstream dependencies and GC pauses.",
    "Inspect memory usage trends and restart leaking instances.",
)


def _seed_for(service: str) -> int:
    """Derive a stable integer seed from a service name.

    Uses a SHA-256 digest so the seed is stable across processes and Python's
    hash randomization, keeping simulated data repeatable for a given service.
    """

    digest = hashlib.sha256(service.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _rng(service: str, *parts: object) -> random.Random:
    """Return a ``random.Random`` seeded from the service plus optional parts.

    Passing extra ``parts`` derives an independent-but-deterministic stream for
    a specific tool, so tools do not consume each other's random sequence while
    remaining repeatable for the same inputs.
    """

    seed = _seed_for(service)
    for part in parts:
        seed ^= _seed_for(str(part))
    return random.Random(seed)


def _error_fraction(service: str) -> float:
    """Deterministic base fraction of ERROR-level log entries for a service.

    This single source of truth ties ``get_recent_logs`` ERROR volume to the
    ``error_rate`` reported by ``get_service_metrics`` so the two are coherent.
    """

    return round(_rng(service, "error-fraction").uniform(0.0, 0.6), 4)


def _base_time(service: str) -> datetime:
    """Return a deterministic, per-service reference instant for timestamps.

    Anchored to :data:`_REFERENCE_TIME` and offset by a seeded amount so each
    service has its own stable "most recent" instant without depending on the
    wall clock (which would break repeatability).
    """

    offset_minutes = _rng(service, "clock").randint(0, 240)
    return _REFERENCE_TIME - timedelta(minutes=offset_minutes)


def get_recent_logs(service: str, limit: int = 50) -> RecentLogs:
    """Return simulated recent log entries for a service.

    The proportion of ERROR entries is governed by :func:`_error_fraction`, the
    same value that drives the metrics ``error_rate``.
    """

    count = max(0, limit)
    rng = _rng(service, "logs")
    error_fraction = _error_fraction(service)
    # WARN sits between the INFO baseline and the ERROR fraction.
    warn_fraction = min(1.0 - error_fraction, error_fraction + 0.15)

    now = _base_time(service)
    entries: list[LogEntry] = []
    for i in range(count):
        roll = rng.random()
        if roll < error_fraction:
            level: LogLevel = "ERROR"
        elif roll < error_fraction + warn_fraction:
            level = "WARN"
        else:
            level = "INFO"
        message = rng.choice(_LOG_MESSAGES[level])
        # Newest first: entry i is i*5..+ seconds in the past.
        ts = now - timedelta(seconds=(i * 5) + rng.randint(0, 4))
        entries.append(
            {
                "timestamp": ts.isoformat(),
                "level": level,
                "message": f"{service}: {message}",
            }
        )
    return {"service": service, "entries": entries}


def get_service_metrics(service: str, window_minutes: int = 15) -> ServiceMetrics:
    """Return simulated service metrics for a service.

    ``error_rate`` is anchored to :func:`_error_fraction` (with small jitter)
    so it plausibly tracks the ERROR log volume; latency, CPU and memory scale
    upward with the error fraction to read like a service under stress.
    """

    rng = _rng(service, "metrics", window_minutes)
    error_fraction = _error_fraction(service)

    jitter = rng.uniform(-0.03, 0.03)
    error_rate = min(1.0, max(0.0, round(error_fraction + jitter, 4)))

    # Higher error fraction -> higher latency / utilisation, plus noise.
    p95_latency_ms = round(80.0 + (error_fraction * 900.0) + rng.uniform(0, 120), 2)
    cpu_pct = round(min(100.0, 20.0 + (error_fraction * 70.0) + rng.uniform(0, 15)), 2)
    memory_pct = round(min(100.0, 30.0 + (error_fraction * 50.0) + rng.uniform(0, 15)), 2)

    return {
        "service": service,
        "metrics": {
            "error_rate": error_rate,
            "p95_latency_ms": p95_latency_ms,
            "cpu_pct": cpu_pct,
            "memory_pct": memory_pct,
        },
    }


def get_incident_history(service: str, limit: int = 10) -> IncidentHistory:
    """Return simulated past resolved incidents for a service."""

    count = max(0, limit)
    rng = _rng(service, "history")
    now = _base_time(service)

    incidents: list[HistoricIncident] = []
    for i in range(count):
        num = rng.randint(1, 9999)
        title_seed = rng.choice(_RUNBOOK_TITLES)
        severity = rng.choice(_SEVERITIES)
        # Resolved progressively further in the past for a coherent history.
        resolved_at = now - timedelta(days=(i + 1), hours=rng.randint(0, 23))
        incidents.append(
            {
                "incident_id": f"INC-{num:04d}",
                "title": f"{service}: {title_seed.lower()}",
                "severity": severity,
                "resolved_at": resolved_at.isoformat(),
            }
        )
    return {"service": service, "incidents": incidents}


def search_runbook(service: str, query: str) -> RunbookSearch:
    """Return simulated runbook matches for a service and free-text query.

    Results are sorted by descending ``score`` so the best match is first.
    """

    rng = _rng(service, "runbook", query)
    match_count = rng.randint(1, 3)

    matches: list[RunbookMatch] = []
    for _ in range(match_count):
        idx = rng.randrange(len(_RUNBOOK_TITLES))
        title = _RUNBOOK_TITLES[idx]
        excerpt = rng.choice(_RUNBOOK_EXCERPTS)
        score = round(rng.uniform(0.3, 0.99), 4)
        matches.append(
            {
                "runbook_id": f"RB-{(idx + 1):03d}",
                "title": title,
                "excerpt": excerpt,
                "score": score,
            }
        )
    matches.sort(key=lambda m: m["score"], reverse=True)
    return {"matches": matches}
