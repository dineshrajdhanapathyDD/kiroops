# Implementation Plan: incident-management

## Overview

This plan builds KiroOps incident-management bottom-up and test-driven: backend scaffolding first, then the pure deterministic core (enums + status state machine), the SQLite Repository_Layer, the incident service and API endpoints, the MCP_Server, and the Diagnosis_Agent with an injected LLM provider. Property-based tests (Hypothesis) validate the six correctness properties from the design close to the code they exercise. Frontend and the real Bedrock/Anthropic provider are marked optional/later so the core backend + MCP + agent + property tests stand alone as the required deliverable.

Each task references the requirements and/or design properties it implements. Tasks marked with `*` are optional test or later-stage sub-tasks.

## Tasks

- [x] 1. Backend project scaffolding
  - [x] 1.1 Create backend package layout and configuration
    - Create `backend/` package structure: `domain/`, `repository/`, `service/`, `api/`, `mcp/`, `agent/`, `tests/`
    - Add project metadata and dependencies (FastAPI-style framework, Hypothesis, pytest) and a test runner config
    - Add a `config` module exposing `LlmConfig` fields (model identifier, endpoint) and a SQLite database path, read from environment with defaults
    - _Requirements: 4.6_

  - [x] 1.2 Create SQLite connection/bootstrap helper
    - Implement a connection factory that opens SQLite and applies schema DDL for `incidents`, `timeline_events`, `diagnoses`, `remediation_actions`
    - Support an in-memory/temporary database for tests
    - _Requirements: 1.1, 6.2_

- [x] 2. Domain model, enums, and pure status state machine
  - [x] 2.1 Define enums and dataclasses
    - Implement `Severity`, `IncidentStatus`, `TimelineEventType` enums per design
    - Implement `Incident`, `TimelineEvent`, `Diagnosis`, `RemediationAction` dataclasses
    - _Requirements: 1.2, 1.4, 6.1_

  - [x] 2.2 Implement pure status state machine
    - Implement `_VALID_TRANSITIONS` allow-list and `is_valid_transition(current, target) -> bool`
    - Ensure same-state, backward, and skip-ahead transitions return `False`
    - _Requirements: 3.1, 3.3, 7.3, 7.4_

  - [x]* 2.3 Write property test for the status state machine
    - **Property 3: Status changes follow the transition state machine**
    - Generate all `(from, target)` `IncidentStatus` pairs; assert only OPEN->INVESTIGATING and INVESTIGATING->RESOLVED return `True`, all others `False`
    - **Validates: Requirements 3.1, 3.3, 7.3, 7.4**

  - [x]* 2.4 Write unit tests for enums and models
    - Test enum string values and dataclass construction defaults
    - _Requirements: 1.4, 6.1_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Repository_Layer over SQLite
  - [x] 4.1 Implement IncidentRepository with INC-#### id generation
    - Implement `create` using `INTEGER PRIMARY KEY AUTOINCREMENT` `num`, deriving `incident_id = "INC-" + str(num).zfill(4)` inside the insert transaction
    - Add `UNIQUE` constraint enforcement on `incident_id` (defense-in-depth)
    - Implement `get`, `list`, `update_status`
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 7.1, 7.2_

  - [x]* 4.2 Write property test for incident ID format, uniqueness, and monotonicity
    - **Property 2: Incident IDs are well-formed, unique, and monotonic**
    - Generate a sequence of N creations; assert every id matches `INC-\d{4,}`, all ids distinct, numeric portions strictly increasing in creation order
    - **Validates: Requirements 1.2, 1.3, 7.1, 7.2**

  - [x] 4.3 Implement TimelineRepository (append-only)
    - Implement `append` computing `seq = max(existing seq) + 1` in a transaction; no update/delete methods
    - Implement `list` ordered by `timestamp` then `seq` (earliest -> latest)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x]* 4.4 Write property test for append-only timeline
    - **Property 4: Timeline is append-only**
    - Snapshot events, append a new event, assert prior events are unchanged and present and timeline grew only by the appended event
    - **Validates: Requirements 6.2**

  - [x]* 4.5 Write property test for chronological timeline ordering
    - **Property 5: Timeline is returned in chronological order**
    - For any set of appended events, assert `list` returns them earliest -> latest by timestamp
    - **Validates: Requirements 2.2, 6.3**

  - [x] 4.6 Implement DiagnosisRepository and RemediationRepository
    - Implement `DiagnosisRepository.save`/`get` and `RemediationRepository.save_all`/`list`
    - _Requirements: 4.4, 5.3_

  - [x]* 4.7 Write unit tests for diagnosis and remediation repositories
    - Test save/get round-trip for diagnosis and save_all/list for remediation actions
    - _Requirements: 4.4, 5.3_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Incident service and timeline policy
  - [x] 6.1 Implement IncidentService create/list/get
    - Validate non-empty/non-whitespace title and enum severity; assign id via repository; set status OPEN; append "created" timeline event
    - Implement list and get-with-timeline; raise not-found for unknown id
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3_

  - [x]* 6.2 Write property test for created incident persisted state
    - **Property 1: Created incident is persisted with initial state**
    - Generate valid `(title, severity, service)`; create then read back; assert fields equal input, status OPEN, first timeline event is "created" with a timestamp
    - **Validates: Requirements 1.1, 1.4, 1.5**

  - [x] 6.3 Implement IncidentService status update
    - Use `is_valid_transition`; on valid, persist new status and append "status changed" event with `{"from", "to"}`; on invalid raise transition error leaving status unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.4_

  - [x]* 6.4 Write unit tests for create validation and status update edge cases
    - Whitespace-only title rejected (Req 1.6); non-enum severity rejected (Req 1.7); invalid/backward transition leaves status unchanged (Req 3.3)
    - _Requirements: 1.6, 1.7, 3.3, 3.4_

- [x] 7. Backend API layer and error handling
  - [x] 7.1 Implement request/response models
    - Implement `CreateIncidentRequest`, `IncidentResponse`, `IncidentSummary`, `TimelineEventModel`, `IncidentDetailResponse`, `UpdateStatusRequest`, `DiagnosisResponse`, `RemediationActionModel`
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 4.2, 5.1, 5.3_

  - [x] 7.2 Implement incident endpoints (create, list, get)
    - `POST /incidents`, `GET /incidents`, `GET /incidents/{id}` wired to IncidentService
    - _Requirements: 1.1, 2.1, 2.2, 2.3_

  - [x] 7.3 Implement status endpoint and error envelope mapping
    - `PATCH /incidents/{id}/status`; map errors to the envelope and codes: 422 title/severity/unknown-status, 404 unknown id, 409 invalid/backward transition
    - _Requirements: 1.6, 1.7, 2.3, 3.3, 3.4, 7.4_

  - [x]* 7.4 Write integration tests for incident endpoints and error table
    - Test each row of the error handling table returns the correct HTTP status and envelope; assert state unchanged on validation/transition failures
    - _Requirements: 1.6, 1.7, 2.3, 3.3, 3.4_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. MCP_Server with simulated evidence tools
  - [~] 9.1 Implement the four MCP tools with seeded simulated data
    - Implement `get_recent_logs`, `get_service_metrics`, `get_incident_history`, `search_runbook` returning the fixed output shapes from the design, generated from a per-service seed for coherent data
    - _Requirements: 4.1_

  - [~] 9.2 Implement McpClient interface used by the agent
    - Expose a client abstraction over the four tools so the Diagnosis_Agent depends on a stable contract and can be stubbed in tests
    - _Requirements: 4.1_

  - [ ]* 9.3 Write unit tests for MCP tool output shapes
    - Assert each tool returns the documented keys/types and that seeded data is coherent across calls in a session
    - _Requirements: 4.1_

- [ ] 10. Diagnosis_Agent with injected LLM provider
  - [~] 10.1 Define LlmProvider protocol, LlmConfig, and result types
    - Implement `LlmProvider` Protocol with `complete`, `LlmUnavailableError`, `LlmResult`, and `DiagnosisResult`/`DiagnosisUnavailable`
    - _Requirements: 4.2, 4.5, 4.6_

  - [~] 10.2 Implement DiagnosisAgent deterministic orchestration
    - Implement `_gather_evidence` (all four MCP tools), `_build_prompt`, `complete` call using configured model/endpoint, `_parse` into diagnosis + remediation actions
    - On `LlmUnavailableError` return `DiagnosisUnavailable` without producing a diagnosis
    - _Requirements: 4.1, 4.2, 4.6, 5.1_

  - [ ]* 10.3 Write property test for LLM unavailability preserving status
    - **Property 6: LLM unavailability preserves incident status**
    - Stub `LlmProvider` to fail; request diagnosis for any incident; assert result is diagnosis-unavailable and status unchanged
    - **Validates: Requirements 4.5**

  - [ ]* 10.4 Write unit tests for agent orchestration success path
    - With stubbed MCP client and stub LlmProvider: assert all four tools invoked, evidence passed, diagnosis parsed, remediation actions derived, configured model/endpoint used
    - _Requirements: 4.1, 4.2, 4.6, 5.1_

  - [~] 10.5 Implement DiagnosisService and diagnosis endpoints
    - Wire `POST /incidents/{id}/diagnosis`: load incident (404 if missing), append "diagnosis requested" event, invoke agent, persist diagnosis + actions, append "actions suggested" event; return 503 on unavailable with status unchanged
    - Wire `GET /incidents/{id}/remediation-actions`
    - _Requirements: 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_

  - [ ]* 10.6 Write integration tests for diagnosis flow
    - Assert "diagnosis requested" and "actions suggested" events appended, diagnosis and actions persisted and retrievable, 503 + unchanged status on unavailable
    - _Requirements: 4.3, 4.4, 4.5, 5.2, 5.3_

- [~] 11. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 12. Real LLM provider integration (optional / later)
  - [ ]* 12.1 Implement Bedrock/Anthropic-backed LlmProvider
    - Build a concrete `LlmProvider` from `LlmConfig` (model id + endpoint); map network/service errors to `LlmUnavailableError`
    - _Requirements: 4.2, 4.5, 4.6_

  - [ ]* 12.2 Write smoke test for provider construction from config
    - Assert provider is constructed with configured model/endpoint; error paths raise `LlmUnavailableError` (mock transport)
    - _Requirements: 4.5, 4.6_

- [ ]* 13. Frontend (TypeScript / React) (optional / later)
  - [ ]* 13.1 Define shared types
    - Implement `types.ts` mirroring backend models (Severity, IncidentStatus, TimelineEventType, Incident, IncidentDetail, RemediationAction, Diagnosis)
    - _Requirements: 2.4, 5.4_

  - [ ]* 13.2 Implement services layer
    - Implement `incidentsApi` (create, list, get, updateStatus, requestDiagnosis, getRemediationActions) with error-envelope mapping
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 4.2, 5.3_

  - [ ]* 13.3 Implement CreateIncidentPage
    - Form with title, severity dropdown, service; client-side rejects empty/whitespace title; surfaces server validation errors
    - _Requirements: 1.6, 1.7_

  - [ ]* 13.4 Implement IncidentListPage
    - Table of incidents showing id, title, severity, service, status
    - _Requirements: 2.1_

  - [ ]* 13.5 Implement IncidentDetailPage
    - Show current status, chronological timeline, Request Diagnosis action, diagnosis, remediation actions, and valid-next-state controls
    - _Requirements: 2.2, 2.4, 5.4_

  - [ ]* 13.6 Write frontend component tests
    - Detail view renders status + chronological timeline (Req 2.4) and each remediation action (Req 5.4)
    - _Requirements: 2.4, 5.4_

- [~] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster core deliverable. The real LLM provider (task 12) and the entire frontend (task 13) are marked optional/later; the required core is backend + MCP + agent + the six property tests.
- Each task references specific requirements and, where applicable, the design correctness property it validates.
- Checkpoints ensure incremental validation as the deterministic core is built before the non-deterministic LLM boundary.
- Property tests use Hypothesis (Python), a minimum of 100 iterations each, against an in-memory/temporary SQLite database. Property 2 (ID format/uniqueness/monotonicity) and Property 3 (status state machine) are the two explicitly called-out invariants.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "2.4"] },
    { "id": 3, "tasks": ["4.1", "4.3", "4.6"] },
    { "id": 4, "tasks": ["4.2", "4.4", "4.5", "4.7"] },
    { "id": 5, "tasks": ["6.1", "6.3"] },
    { "id": 6, "tasks": ["6.2", "6.4"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3"] },
    { "id": 9, "tasks": ["7.4", "9.1"] },
    { "id": 10, "tasks": ["9.2", "9.3"] },
    { "id": 11, "tasks": ["10.1"] },
    { "id": 12, "tasks": ["10.2"] },
    { "id": 13, "tasks": ["10.3", "10.4", "10.5"] },
    { "id": 14, "tasks": ["10.6", "12.1", "13.1"] },
    { "id": 15, "tasks": ["12.2", "13.2"] },
    { "id": 16, "tasks": ["13.3", "13.4", "13.5"] },
    { "id": 17, "tasks": ["13.6"] }
  ]
}
```
