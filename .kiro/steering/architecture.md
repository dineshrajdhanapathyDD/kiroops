# Architecture

KiroOps follows a layered architecture. Data flows in one direction through
the layers; lower layers never call upward.

```
Frontend (React/TypeScript)
    -> Backend API (FastAPI routers)
        -> Service layer (business rules)
            -> Repository layer (SQLite)
Diagnosis Agent
    -> MCP Server tools (logs, metrics, history, runbook)
    -> LLM Provider (Bedrock/Anthropic)
```

## Layers and Responsibilities

- Backend API layer: validates request shapes, maps to service calls,
  serializes responses and errors. No business logic here.
- Service layer: all deterministic business rules live here - incident ID
  assignment, status transition validation, timeline append policy, diagnosis
  orchestration entry point.
- Repository layer: the only code that touches SQLite. Enforces append-only
  timeline and unique/monotonic IDs at the storage boundary.
- Diagnosis Agent: deterministic orchestration that gathers evidence via MCP
  tools, then calls the LLM. The model call is the only non-deterministic step.
- MCP Server: custom server exposing get_recent_logs, get_service_metrics,
  get_incident_history, search_runbook. Returns simulated seeded data.
- LLM Provider: an injected interface, configured by model id and endpoint.

## Rules

- Keep business logic out of API routes. Routes call services; services own
  the rules.
- Use typed interfaces and models at every boundary (Pydantic models on the
  backend, TypeScript types on the frontend).
- Never hard-code credentials, model ids, or endpoints. Read them from
  configuration/environment.
- All external integrations (LLM, MCP) must have explicit error handling and a
  defined behavior when the dependency is unavailable.
- The LLM is a non-deterministic boundary. Isolate it behind an injected
  provider so the deterministic core is testable without a live model.
- The timeline is append-only. The repository exposes append and list only -
  no update or delete for timeline events.

## Component Map (repo layout)

- backend/  - Python service (domain, repository, service, api, mcp, agent)
- mcp/      - custom MCP server (Lesson 6)
- powers/   - Incident Analysis Power (Lesson 5 / bonus)
- frontend/ - React/TypeScript dashboard
- .kiro/    - specs, steering, hooks, agents, settings (the lesson evidence)