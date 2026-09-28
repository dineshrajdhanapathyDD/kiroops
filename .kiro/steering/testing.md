# Testing

KiroOps uses a dual testing strategy: example/unit tests for specific
behaviors, and property-based tests for universal invariants. This directly
supports Kiro University Lesson 4 (property-based testing).

## Frameworks

- Backend: pytest for unit/integration tests, Hypothesis for property tests.
- Frontend: component tests for rendering behavior.

## Property-Based Tests (Hypothesis)

- Each property test runs a minimum of 100 generated iterations.
- Run against an in-memory or temporary SQLite database, never a shared file.
- Tag each property test with its property number and text, e.g.
  "Feature: incident-management, Property 2: Incident IDs are well-formed,
  unique, and monotonic".

The six correctness properties from the design each have a dedicated property
test:

1. Created incident is persisted with initial state (status OPEN, first event
   is "created").
2. Incident IDs are non-empty, match INC-\d{4,}, unique, and monotonic.
3. Status changes follow the state machine: only OPEN->INVESTIGATING and
   INVESTIGATING->RESOLVED succeed; all others are rejected and status is
   preserved.
4. Timeline is append-only: prior events are never modified or removed.
5. Timeline is returned earliest -> latest.
6. LLM unavailability preserves incident status (returns diagnosis-unavailable,
   state unchanged).

Properties 2 and 3 are the two explicitly called-out invariants and must always
be present and passing.

## Testability Rules

- The LLM provider is injected. In tests it is stubbed to return canned output
  (success path) or raise LlmUnavailableError (unavailable path). No test hits
  a live model.
- The MCP client is stubbed in agent tests so orchestration is verified against
  a stable contract.
- Deterministic units (is_valid_transition, id derivation, prompt building,
  response parsing) are tested in isolation.

## Definition of Done for a Task

- New behavior has at least one test.
- Any invariant it touches has (or already has) a property test.
- The full test suite passes before the task is marked complete.