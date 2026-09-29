# incident-mcp

A standalone Model Context Protocol (MCP) server that exposes the four KiroOps
incident evidence-gathering tools. Built with the official Python MCP SDK
(`FastMCP`). This is the Kiro University Lesson 6 deliverable.

**All data returned by these tools is simulated.** It is generated
deterministically from a per-service seed (see `backend/mcp/tools.py`, the
single source of truth), so repeated calls for the same service are coherent
and repeatable. No external systems, databases, or live logs are contacted.

## Tools

| Tool | Input | Output |
|------|-------|--------|
| `get_recent_logs` | `service: str, limit: int = 50` | `{ "service", "entries": [ { "timestamp", "level": "INFO\|WARN\|ERROR", "message" } ] }` |
| `get_service_metrics` | `service: str, window_minutes: int = 15` | `{ "service", "metrics": { "error_rate", "p95_latency_ms", "cpu_pct", "memory_pct" } }` |
| `get_incident_history` | `service: str, limit: int = 10` | `{ "service", "incidents": [ { "incident_id", "title", "severity", "resolved_at" } ] }` |
| `search_runbook` | `service: str, query: str` | `{ "matches": [ { "runbook_id", "title", "excerpt", "score" } ] }` |

The metrics `error_rate` intentionally tracks the volume of `ERROR` entries
returned by `get_recent_logs` for the same service, so the evidence reads
coherently.

## Install

From this directory:

```bash
pip install -r requirements.txt
```

This installs the `mcp` SDK. The tool logic itself is pure Python and lives in
`backend/mcp/tools.py`; this server reuses it (it does not re-implement the
seeding).

## Run

```bash
python server.py
```

or, with the MCP CLI installed:

```bash
mcp run server.py
```

The server communicates over stdio, which is how Kiro launches it (see
`.kiro/settings/mcp.json` at the workspace root).

## Layout

```
mcp/incident-mcp/
  server.py            FastMCP server; registers the four tools
  _shared.py           puts the workspace root on sys.path so `backend` imports
  tools/
    logs.py            thin wrapper -> backend.mcp.tools.get_recent_logs
    metrics.py         thin wrapper -> backend.mcp.tools.get_service_metrics
    incidents.py       thin wrappers -> get_incident_history / search_runbook
  requirements.txt     declares the mcp SDK
  README.md            this file
```

The wrappers delegate to `backend/mcp/tools.py` so the seeded data-generation
logic is never duplicated across two divergent copies.
