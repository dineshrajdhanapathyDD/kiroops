# Coding Standards

## General

- Prefer clear, small, single-responsibility functions over large ones.
- Match existing patterns in the file and module before introducing new ones.
- No hard-coded secrets, endpoints, or model ids. Use configuration.
- Validate input at the boundary; keep the core assuming valid data.
- Fail loudly on programmer errors; fail gracefully on external ones.

## Python (backend, MCP, agent)

- Target Python 3.11+.
- Use type hints on all public functions and dataclass/Pydantic models.
- Use enums for closed sets: Severity, IncidentStatus, TimelineEventType.
- Domain objects are dataclasses; API request/response are Pydantic models.
- Raise typed domain errors (e.g. InvalidTransitionError, NotFoundError,
  LlmUnavailableError); map them to HTTP codes in the API layer only.
- The status state machine lives in one pure function, is_valid_transition,
  which is the sole authority for transitions.
- Repository methods own transactions. Timeline supports append and list only.
- Keep the Diagnosis Agent orchestration deterministic; the LLM call is the
  only non-deterministic step and must sit behind an injected provider.
- Format with a standard formatter (black-style). Keep imports ordered.

## TypeScript / React (frontend)

- Strict TypeScript. No implicit any.
- Shared types in types.ts mirror the backend response models.
- All HTTP calls go through the services layer (api/). Components stay
  presentational and receive data via props/hooks.
- Map backend error envelopes to user-facing messages in the services layer.

## Error Envelope (shared contract)

All API errors use: { "error": { "code": str, "message": str, "field"?: str } }

| Condition                   | HTTP |
|-----------------------------|------|
| Validation (title/severity) | 422  |
| Unknown incident id         | 404  |
| Invalid status transition   | 409  |
| Unknown status value        | 422  |
| LLM unavailable             | 503  |

## Naming

- incident_id format: INC-#### (zero-padded, matches INC-\d{4,}).
- Files and modules: snake_case (Python), camelCase for TS variables,
  PascalCase for React components and TS types.