# Design Document

## Overview

KiroOps incident-management is a layered application for creating, tracking, and resolving operational incidents, augmented by an AI diagnosis agent. This design realizes the requirements in `requirements.md`: operators create incidents (Req 1), view them (Req 2), advance status through a constrained lifecycle (Req 3), request an evidence-based AI diagnosis (Req 4) with derived remediation actions (Req 5), all backed by an append-only timeline (Req 6) and two explicitly verifiable invariants (Req 7).

The system is split into a Python (FastAPI-style) Backend_Service persisting to local SQLite through a Repository_Layer, a TypeScript/React Frontend_App, a custom MCP_Server exposing evidence-gathering tools that return simulated realistic data, and a Diagnosis_Agent that orchestrates evidence gathering and a call to a real LLM_Provider (Bedrock/Anthropic). The LLM_Provider is treated as a non-deterministic external boundary: its model and endpoint are configurable and its unavailability is handled gracefully.

The design keeps deterministic logic (ID generation, status state machine, timeline appends, orchestration sequencing) strictly separated from non-deterministic logic (the LLM call), so the deterministic core is fully unit- and property-testable without a live model. This directly serves the Kiro University goal of a reviewable, spec-driven, testable feature.

## Architecture

### Layered Design

```
+-------------------------------------------------------------+
|                       Frontend_App                          |
|         (TypeScript / React: pages + components)            |
|   Create Incident | Incident List | Incident Detail         |
|                    api/ services layer                      |
+---------------------------+---------------------------------+
                            | HTTP (JSON)
                            v
+-------------------------------------------------------------+
|                      Backend API layer                      |
|            (FastAPI routers: request/response models)       |
|  POST /incidents  GET /incidents  GET /incidents/{id}       |
|  PATCH /incidents/{id}/status                               |
|  POST /incidents/{id}/diagnosis                             |
|  GET  /incidents/{id}/remediation-actions                   |
+---------------------------+---------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|                       Service layer                         |
|  IncidentService | StatusStateMachine | TimelineService     |
|  DiagnosisService (invokes Diagnosis_Agent)                 |
+------------------+--------------------+---------------------+
                   |                    |
                   v                    v
+-----------------------------+   +-----------------------------+
|       Repository_Layer      |   |      Diagnosis_Agent        |
|  IncidentRepository         |   |  (deterministic             |
|  TimelineRepository         |   |   orchestration)            |
|  DiagnosisRepository        |   +--------+----------+---------+
|  RemediationRepository      |            |          |
+--------------+--------------+            v          v
               |                    +-------------+  +--------------+
               v                    | MCP_Server  |  | LLM_Provider |
        +-------------+             |  tools      |  | (Bedrock/    |
        |   SQLite    |             | (simulated) |  |  Anthropic)  |
        +-------------+             +-------------+  +--------------+
```

### Component Responsibilities

- **Frontend_App** (Req 2.4, 5.4): renders create/list/detail views; calls the Backend API through a typed services layer.
- **Backend API layer** (Req 1, 2, 3, 4, 5): validates request shapes, maps to service calls, serializes responses and errors.
- **Service layer** (Req 1-6): holds all deterministic business rules â€” ID assignment, status transition validation, timeline append policy, and diagnosis orchestration entry point.
- **Repository_Layer** (Req 1.1, 2.1-2.2, 3.1, 4.4, 6.2): the only component that touches SQLite; enforces append-only timeline and unique/monotonic IDs at the storage boundary.
- **Diagnosis_Agent** (Req 4, 5): deterministic orchestration that gathers evidence via MCP_Server tools then calls the LLM_Provider; separated from the model call for testability.
- **MCP_Server** (Req 4.1): exposes `get_recent_logs`, `get_service_metrics`, `get_incident_history`, `search_runbook`, returning simulated realistic data.
- **LLM_Provider** (Req 4.2, 4.5, 4.6): non-deterministic boundary, configured by model id and endpoint, may be unavailable.

### Diagnosis Sequence (Req 4, 5)

```
Operator -> POST /incidents/{id}/diagnosis -> DiagnosisService
  DiagnosisService: load incident (404 if missing)                # Req 2.3
  append "diagnosis requested" timeline event                     # Req 4.3
  Diagnosis_Agent.diagnose(service):
     evidence = {
        logs    = MCP.get_recent_logs(service)                    # Req 4.1
        metrics = MCP.get_service_metrics(service)
        history = MCP.get_incident_history(service)
        runbook = MCP.search_runbook(service, title)
     }
     result = LLM_Provider.complete(model, endpoint, evidence)    # Req 4.2, 4.6
     if LLM error/unavailable: return DiagnosisUnavailable        # Req 4.5
     diagnosis = parse(result); actions = derive(result)          # Req 5.1
  persist diagnosis                                               # Req 4.4
  persist remediation actions
  append "actions suggested" timeline event                       # Req 5.2
  (status is never changed by diagnosis)                          # Req 4.5
```

## Components and Interfaces

### API Endpoints and Models

All request/response bodies are JSON. Models are shown as Pydantic-style dataclasses.

#### Enums

```python
class Severity(str, Enum):
    LOW = "LOW"; MEDIUM = "MEDIUM"; HIGH = "HIGH"; CRITICAL = "CRITICAL"

class IncidentStatus(str, Enum):
    OPEN = "OPEN"; INVESTIGATING = "INVESTIGATING"; RESOLVED = "RESOLVED"

class TimelineEventType(str, Enum):
    CREATED = "created"
    STATUS_CHANGED = "status changed"
    DIAGNOSIS_REQUESTED = "diagnosis requested"
    ACTIONS_SUGGESTED = "actions suggested"
```

#### POST /incidents â€” Create Incident (Req 1)

Request:
```python
class CreateIncidentRequest(BaseModel):
    title: str        # non-empty, non-whitespace       (Req 1.6)
    severity: Severity                                    # (Req 1.7)
    service: str
```
Response `201`:
```python
class IncidentResponse(BaseModel):
    incident_id: str          # INC-####                 (Req 1.2)
    title: str
    severity: Severity
    service: str
    status: IncidentStatus    # OPEN on creation         (Req 1.4)
    created_at: str           # ISO-8601 timestamp
```
Behavior: validate title/severity, assign ID, set status OPEN, append "created" event (Req 1.1-1.5).

#### GET /incidents â€” List Incidents (Req 2.1)

Response `200`: `list[IncidentSummary]`
```python
class IncidentSummary(BaseModel):
    incident_id: str
    title: str
    severity: Severity
    service: str
    status: IncidentStatus
```

#### GET /incidents/{incident_id} â€” Get Incident with Timeline (Req 2.2, 2.3, 6.3)

Response `200`:
```python
class TimelineEventModel(BaseModel):
    type: TimelineEventType
    timestamp: str            # ISO-8601
    details: dict             # e.g. {"from": "OPEN", "to": "INVESTIGATING"}

class IncidentDetailResponse(IncidentResponse):
    timeline: list[TimelineEventModel]   # earliest -> latest   (Req 6.3)
```
`404` not-found if the id does not exist (Req 2.3).

#### PATCH /incidents/{incident_id}/status â€” Update Status (Req 3)

Request:
```python
class UpdateStatusRequest(BaseModel):
    status: IncidentStatus    # target state
```
Response `200`: `IncidentResponse` with updated status.
- Valid_Transition -> update + persist + "status changed" event (Req 3.1, 3.2).
- Invalid/backward transition -> `409` transition error, status unchanged (Req 3.3).
- Unknown status value -> `422` validation error, status unchanged (Req 3.4).

#### POST /incidents/{incident_id}/diagnosis â€” Request Diagnosis (Req 4)

Response `200`:
```python
class DiagnosisResponse(BaseModel):
    incident_id: str
    summary: str
    evidence_refs: list[str]  # references to gathered evidence  (Req 4.2)
    remediation_actions: list[RemediationActionModel]           # (Req 5.1)
```
`503` diagnosis-unavailable when the LLM_Provider fails; incident status is left unchanged (Req 4.5).

#### GET /incidents/{incident_id}/remediation-actions â€” Get Actions (Req 5.3)

Response `200`: `list[RemediationActionModel]`
```python
class RemediationActionModel(BaseModel):
    action_id: str
    description: str
    rationale: str
```

## Data Models

```python
@dataclass
class Incident:
    incident_id: str          # INC-\d{4,}                       (Req 1.2, 7.1)
    title: str
    severity: Severity
    service: str
    status: IncidentStatus
    created_at: datetime

@dataclass
class TimelineEvent:
    incident_id: str
    seq: int                  # append order within incident
    type: TimelineEventType                                     # (Req 6.1)
    timestamp: datetime
    details: dict             # structured payload per event type

@dataclass
class Diagnosis:
    incident_id: str
    summary: str
    evidence_refs: list[str]
    created_at: datetime

@dataclass
class RemediationAction:
    action_id: str
    incident_id: str
    description: str
    rationale: str
```

### Incident ID Generation Strategy (Req 1.2, 1.3, 7.1, 7.2)

Format: `INC-` followed by the incident's numeric portion zero-padded to at least 4 digits, matching `INC-\d{4,}`. Example: the 1st incident is `INC-0001`, the 10000th is `INC-10000` (padding is a minimum width, so monotonicity is preserved beyond 4 digits).

Uniqueness and monotonicity are guaranteed at the SQLite boundary rather than in application memory:

- The `incidents` table uses an `INTEGER PRIMARY KEY AUTOINCREMENT` column `num`. SQLite's `AUTOINCREMENT` guarantees each inserted row receives a value strictly greater than any previously used value in that table, and never reuses a value even after deletes. This yields a strictly increasing numeric sequence (monotonic numeric portion â€” Req 1.3).
- The displayed `incident_id` is derived deterministically as `"INC-" + str(num).zfill(4)`. Because `num` is unique and strictly increasing, `incident_id` is unique (Req 1.2, 7.2) and its numeric portion is strictly greater than every prior one (Req 1.3).
- A `UNIQUE` constraint on `incident_id` is added as a defense-in-depth guard so any accidental duplicate insert fails loudly (Req 7.2).
- The ID is assigned inside the same transaction as the incident insert, so concurrent creates cannot observe or reuse the same `num`.

This makes the format, uniqueness, and monotonicity invariants storage-enforced and directly checkable by the property test in the testing section.

### Status State Machine (Req 3, 7.3, 7.4)

A single pure validation function is the sole authority for transitions:

```python
_VALID_TRANSITIONS = {
    (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING),
    (IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED),
}

def is_valid_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    """Return True only for forward-adjacent transitions.
    Rejects same-state, backward, skip-ahead (OPEN->RESOLVED), and
    any transition not in the allow-list."""
    return (current, target) in _VALID_TRANSITIONS
```

- The allow-list contains exactly the two Valid_Transitions. Everything else (same-state `OPEN->OPEN`, backward `RESOLVED->INVESTIGATING`, skip `OPEN->RESOLVED`) returns `False` (Req 3.3, 7.3).
- Unknown/undefined status strings never reach this function: the API layer deserializes `status` into the `IncidentStatus` enum first; an unrecognized value yields a `422` validation error before any state change (Req 3.4).
- The service calls `is_valid_transition` before persisting. On `False` it raises `InvalidTransitionError` and performs no write, so the stored status is preserved (Req 3.3, 7.4). On `True` it persists the new status and appends a "status changed" event carrying `{"from": current, "to": target}` (Req 3.1, 3.2).

Centralizing the rule in one pure function makes the state-machine property test exhaustive over all `(from, target)` pairs.

### Repository_Layer over SQLite (Req 1.1, 2.1-2.2, 3.1, 4.4, 6.2)

Four tables, with the timeline modeled append-only:

```sql
CREATE TABLE incidents (
    num          INTEGER PRIMARY KEY AUTOINCREMENT,   -- monotonic source (Req 1.3)
    incident_id  TEXT NOT NULL UNIQUE,                -- INC-#### (Req 1.2, 7.2)
    title        TEXT NOT NULL,
    severity     TEXT NOT NULL,
    service      TEXT NOT NULL,
    status       TEXT NOT NULL,                       -- current status (Req 3.1)
    created_at   TEXT NOT NULL
);

CREATE TABLE timeline_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    seq          INTEGER NOT NULL,                    -- append order
    type         TEXT NOT NULL,                       -- (Req 6.1)
    timestamp    TEXT NOT NULL,
    details      TEXT NOT NULL,                       -- JSON payload
    UNIQUE (incident_id, seq)
);

CREATE TABLE diagnoses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    summary      TEXT NOT NULL,
    evidence_refs TEXT NOT NULL,                      -- JSON array
    created_at   TEXT NOT NULL
);

CREATE TABLE remediation_actions (
    action_id    TEXT PRIMARY KEY,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    description  TEXT NOT NULL,
    rationale    TEXT NOT NULL
);
```

Repository interfaces:

```python
class IncidentRepository:
    def create(self, title, severity, service, created_at) -> Incident: ...   # assigns INC-#### (Req 1.1-1.3)
    def get(self, incident_id) -> Incident | None: ...                         # (Req 2.2, 2.3)
    def list(self) -> list[Incident]: ...                                      # (Req 2.1)
    def update_status(self, incident_id, new_status) -> None: ...              # (Req 3.1)

class TimelineRepository:
    def append(self, incident_id, type, timestamp, details) -> None: ...       # append-only (Req 6.2)
    def list(self, incident_id) -> list[TimelineEvent]: ...                    # ordered (Req 6.3)

class DiagnosisRepository:
    def save(self, diagnosis) -> None: ...                                     # (Req 4.4)
    def get(self, incident_id) -> Diagnosis | None: ...

class RemediationRepository:
    def save_all(self, actions) -> None: ...
    def list(self, incident_id) -> list[RemediationAction]: ...                # (Req 5.3)
```

Append-only enforcement (Req 6.2): the Repository_Layer exposes only `append` and `list` for timeline events â€” no update or delete methods exist. Each append computes `seq = max(existing seq) + 1` inside a transaction, so prior events are never modified or removed. `list` returns events ordered by `timestamp` then `seq` (earliest -> latest, Req 6.3), which also gives a stable order for events sharing a timestamp.

## MCP_Server (Req 4.1)

A custom MCP server exposing four tools. Each returns simulated realistic data (deterministic-enough for demos, seeded per service) so the diagnosis flow is exercisable without external systems.

| Tool | Input | Output |
|------|-------|--------|
| `get_recent_logs` | `{ "service": str, "limit": int = 50 }` | `{ "service": str, "entries": [ { "timestamp": str, "level": "INFO\|WARN\|ERROR", "message": str } ] }` |
| `get_service_metrics` | `{ "service": str, "window_minutes": int = 15 }` | `{ "service": str, "metrics": { "error_rate": float, "p95_latency_ms": float, "cpu_pct": float, "memory_pct": float } }` |
| `get_incident_history` | `{ "service": str, "limit": int = 10 }` | `{ "service": str, "incidents": [ { "incident_id": str, "title": str, "severity": str, "resolved_at": str } ] }` |
| `search_runbook` | `{ "service": str, "query": str }` | `{ "matches": [ { "runbook_id": str, "title": str, "excerpt": str, "score": float } ] }` |

Simulated data is generated from a per-service seed so repeated calls in a session are coherent (e.g. metrics that plausibly match log ERROR volume). The tool contracts (input/output shapes) are fixed so the Diagnosis_Agent can depend on them and be tested against stubs.

## Diagnosis_Agent (Req 4, 5)

### Orchestration Flow

The agent is a deterministic orchestrator with one non-deterministic dependency (the LLM_Provider). It performs:

1. Gather evidence by invoking all four MCP tools for the incident's service (Req 4.1).
2. Assemble a structured prompt/context from the gathered evidence.
3. Call `LLM_Provider.complete(...)` with the configured model and endpoint (Req 4.2, 4.6).
4. On success, parse the model output into a `Diagnosis` (summary + `evidence_refs`) and derive `RemediationAction`s (Req 4.2, 5.1).
5. On any LLM error/unavailability, return a `DiagnosisUnavailable` result without producing a diagnosis (Req 4.5).

### Separation of Deterministic Orchestration from the Model Call (testability)

The LLM_Provider is an injected interface, not a concrete client:

```python
class LlmProvider(Protocol):
    def complete(self, prompt: str) -> LlmResult: ...   # may raise LlmUnavailableError

@dataclass
class LlmConfig:
    model_id: str        # configured (Req 4.6)
    endpoint: str        # configured (Req 4.6)

class DiagnosisAgent:
    def __init__(self, mcp_client: McpClient, llm: LlmProvider): ...
    def diagnose(self, incident: Incident) -> DiagnosisResult:
        evidence = self._gather_evidence(incident.service)   # deterministic (Req 4.1)
        prompt   = self._build_prompt(incident, evidence)    # deterministic
        try:
            raw = self.llm.complete(prompt)                  # non-deterministic boundary
        except LlmUnavailableError:
            return DiagnosisUnavailable()                    # (Req 4.5)
        return self._parse(raw)                              # deterministic (Req 4.2, 5.1)
```

- `_gather_evidence`, `_build_prompt`, and `_parse` are pure/deterministic and unit-testable in isolation.
- The only non-deterministic step is `llm.complete`. In tests, `LlmProvider` is replaced with a stub returning canned output (success path) or raising `LlmUnavailableError` (unavailable path), so the full orchestration â€” including the "status unchanged on failure" invariant â€” is verifiable without a live model.
- Real deployment injects a Bedrock/Anthropic-backed `LlmProvider` built from `LlmConfig` (Req 4.6).

## Frontend Design (TypeScript / React)

### Pages / Components

- `CreateIncidentPage` (Req 1): form with title, severity dropdown (LOW/MEDIUM/HIGH/CRITICAL), service field; client-side rejects empty/whitespace title before submit and surfaces server validation errors.
- `IncidentListPage` (Req 2.1): table of incidents showing id, title, severity, service, status.
- `IncidentDetailPage` (Req 2.2, 2.4, 5.4): shows current status, the timeline in chronological order, a "Request Diagnosis" action, the resulting diagnosis, and the list of remediation actions. Includes status-advance controls that only offer valid next states.

### Services Layer and Types

```typescript
// types.ts
export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IncidentStatus = "OPEN" | "INVESTIGATING" | "RESOLVED";
export type TimelineEventType =
  | "created" | "status changed" | "diagnosis requested" | "actions suggested";

export interface TimelineEvent { type: TimelineEventType; timestamp: string; details: Record<string, unknown>; }
export interface Incident {
  incidentId: string; title: string; severity: Severity;
  service: string; status: IncidentStatus; createdAt: string;
}
export interface IncidentDetail extends Incident { timeline: TimelineEvent[]; }
export interface RemediationAction { actionId: string; description: string; rationale: string; }
export interface Diagnosis { incidentId: string; summary: string; evidenceRefs: string[]; remediationActions: RemediationAction[]; }

// api/incidents.ts  (services layer for API calls)
export const incidentsApi = {
  create(req: { title: string; severity: Severity; service: string }): Promise<Incident>,
  list(): Promise<Incident[]>,
  get(id: string): Promise<IncidentDetail>,
  updateStatus(id: string, status: IncidentStatus): Promise<Incident>,
  requestDiagnosis(id: string): Promise<Diagnosis>,
  getRemediationActions(id: string): Promise<RemediationAction[]>,
};
```

The services layer centralizes HTTP calls and error mapping so components stay presentational, and the shared `types.ts` mirrors the backend response models.

## Error Handling

| Condition | Source | HTTP | Response | Requirement |
|-----------|--------|------|----------|-------------|
| Empty/whitespace title | Create validation | 422 | validation error naming `title` | 1.6 |
| Invalid severity | Create validation | 422 | validation error naming `severity` | 1.7 |
| Unknown incident id | Get / status / diagnosis | 404 | not-found error | 2.3 |
| Invalid/backward transition | Status update | 409 | transition error; status unchanged | 3.3, 7.4 |
| Unknown status value | Status update | 422 | validation error; status unchanged | 3.4 |
| LLM unavailable/error | Diagnosis | 503 | diagnosis-unavailable; status unchanged | 4.5 |

Errors use a consistent envelope `{ "error": { "code": str, "message": str, "field": str? } }`. The Frontend services layer maps these codes to user-facing messages. Validation and transition failures never mutate persisted state, preserving the invariants in Req 3 and 7.

## Testing Strategy

A dual approach: example/unit tests for specific behaviors and integration points, and property-based tests for the two explicitly called-out invariants and other universal properties. Backend property tests use **Hypothesis** (Python), each running a minimum of 100 iterations against an in-memory/temporary SQLite database. Frontend components use example-based component tests.

### Unit / Example / Integration Tests

- Create validation edge cases: whitespace-only titles rejected (Req 1.6); non-enum severity rejected (Req 1.7).
- Not-found retrieval returns 404 (Req 2.3).
- Diagnosis orchestration with a stubbed MCP client and stub `LlmProvider`: all four MCP tools invoked (Req 4.1); evidence passed and diagnosis persisted (Req 4.2, 4.4); "diagnosis requested" and "actions suggested" events appended (Req 4.3, 5.2); remediation actions produced and retrievable (Req 5.1, 5.3); configured model/endpoint used (Req 4.6, smoke).
- Frontend component tests: detail view renders status + chronological timeline (Req 2.4) and each remediation action (Req 5.4).

### Property-Based Tests (Hypothesis)

Each property test is tagged **Feature: incident-management, Property {number}: {property_text}** and references its design property. The two called-out properties are Property 2 (ID format/uniqueness) and Property 3 (status state machine).

- **Property 2** â€” generate a sequence of N valid creations; assert every `incident_id` matches `INC-\d{4,}`, all ids are distinct, and numeric portions are strictly increasing in creation order.
- **Property 3** â€” generate all `(from, target)` status pairs (including invalid, backward, same-state, and unknown values); assert valid pairs succeed and persist, and every other pair is rejected with the status preserved.
- **Property 1** â€” generate valid `(title, severity, service)`; create; read back and assert persisted fields equal input, status is OPEN, and the first timeline event is "created".
- **Property 4** â€” snapshot an incident timeline, perform an operation, and assert prior events are byte-for-byte unchanged (append-only).
- **Property 5** â€” for any incident with events, the returned timeline is ordered earliest -> latest.
- **Property 6** â€” with the `LlmProvider` stubbed to fail, request diagnosis for any incident and assert the result is diagnosis-unavailable and the status is unchanged.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system - essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Created incident is persisted with initial state

*For any* valid creation input (non-empty title, valid Severity, service), creating an Incident then reading it back yields an Incident whose title, severity, and service equal the input, whose status is OPEN, and whose timeline begins with a "created" event bearing a timestamp.

**Validates: Requirements 1.1, 1.4, 1.5**

### Property 2: Incident IDs are well-formed, unique, and monotonic

*For any* sequence of Incident creations, every assigned Incident_ID is non-empty and matches `INC-\d{4,}`, all Incident_IDs are pairwise distinct, and each newly assigned Incident_ID has a numeric portion strictly greater than every previously assigned Incident_ID numeric portion.

**Validates: Requirements 1.2, 1.3, 7.1, 7.2**

### Property 3: Status changes follow the transition state machine

*For any* Incident and any requested target status, the change is applied and persisted (with a "status changed" event recording previous and new status) if and only if it is a Valid_Transition (OPEN -> INVESTIGATING or INVESTIGATING -> RESOLVED); for every other requested change (backward, same-state, skip-ahead, or unknown value) the request is rejected and the existing Incident_Status is preserved.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 7.3, 7.4**

### Property 4: Timeline is append-only

*For any* Incident and any operation that records a Timeline_Event, all previously recorded Timeline_Events remain unchanged and present, and the timeline grows only by appended events.

**Validates: Requirements 6.2**

### Property 5: Timeline is returned in chronological order

*For any* Incident, retrieving its Timeline returns the Timeline_Events ordered from earliest to latest by timestamp.

**Validates: Requirements 2.2, 6.3**

### Property 6: LLM unavailability preserves incident status

*For any* existing Incident, when the LLM_Provider is unavailable or returns an error during a diagnosis request, the Diagnosis_Agent returns a diagnosis-unavailable result and the Incident_Status is left unchanged.

**Validates: Requirements 4.5**
