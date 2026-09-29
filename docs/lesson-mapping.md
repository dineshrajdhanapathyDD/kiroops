# Kiro University Lesson Mapping

This project (KiroOps) demonstrates all seven Kiro University lessons. Each
lesson is implemented as a real part of the development workflow. Use the table
below to find the evidence for each lesson by path.

| Lesson | Feature | Where to look (path) |
|--------|---------|----------------------|
| 1. Spec-driven development | requirements -> design -> tasks | `.kiro/specs/incident-management/requirements.md`, `design.md`, `tasks.md` |
| 2. Steering | persistent project guidance | `.kiro/steering/product.md`, `architecture.md`, `coding-standards.md`, `testing.md` |
| 3. Hooks | lint/test automation on file events | `.kiro/hooks/` (see `lint-on-save.json`, `test-on-change.json`) |
| 4. Property-based testing | Hypothesis tests for the 6 correctness properties | `backend/tests/` (files ending in `_property.py`) |
| 5. Powers | Incident Analysis Power (package + skill) | `powers/incident-analysis/` |
| 6. MCP | custom MCP server with 4 evidence tools | `mcp/incident-mcp/` and `.kiro/settings/mcp.json` |
| 7. Custom Agent | Incident Commander agent config | `.kiro/agents/incident-agent.json` |

## Lesson 4 property tests, by property

The design defines six correctness properties (see
`.kiro/specs/incident-management/design.md`, "Correctness Properties"). Each is
backed by a Hypothesis test:

| Property | Statement (short) | Test file |
|----------|-------------------|-----------|
| 1 | Created incident persisted with initial state (OPEN, first event "created") | `backend/tests/test_incident_service_property.py` |
| 2 | Incident IDs well-formed (INC-####), unique, monotonic | `backend/tests/test_incident_repository_property.py` |
| 3 | Status changes follow the state machine | `backend/tests/test_status_machine_property.py` |
| 4 | Timeline is append-only | `backend/tests/test_timeline_repository_property.py` |
| 5 | Timeline returned in chronological order | `backend/tests/test_timeline_repository_property.py` |
| 6 | LLM unavailability preserves incident status | `backend/tests/test_diagnosis_unavailable_property.py` |

Each property test is tagged in-file as
`Feature: incident-management, Property N: ...` and runs a minimum of 100
generated examples.

## Why the folders are not named "lesson-1", "lesson-2", ...

Kiro recognizes specific folders by fixed names (`.kiro/specs`, `.kiro/steering`,
`.kiro/hooks`, `.kiro/agents`, `.kiro/settings`). Renaming them would break Kiro
integration, the MCP server wiring, and progress tracking. This document is the
name-based index instead, so a reviewer can jump straight to any lesson's
evidence without renaming anything.

## Running the backend tests (Lesson 4 evidence)

```
cd backend
py -m pytest -q
```

All property and unit tests should pass.