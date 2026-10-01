# KiroOps

AI-powered incident investigation platform for developers, built for the Kiro
University Challenge. A developer submits an incident (title, service,
severity); KiroOps tracks it through a constrained lifecycle, gathers evidence
through a custom MCP server, produces an AI diagnosis with recommended
remediation actions, and maintains an append-only incident timeline.

## Kiro University Lesson Mapping

| Lesson | Feature | Evidence (path) |
|--------|---------|-----------------|
| 1. Spec-driven development | requirements -> design -> tasks | `.kiro/specs/incident-management/` |
| 2. Steering | persistent project guidance | `.kiro/steering/` |
| 3. Hooks | lint/test automation | `.kiro/hooks/` |
| 4. Property-based testing | Hypothesis property tests (6 properties) | `backend/tests/*_property.py` |
| 5. Powers | Incident Analysis Power | `powers/incident-analysis/` |
| 6. MCP | custom MCP server (4 tools) | `mcp/incident-mcp/` + `.kiro/settings/mcp.json` |
| 7. Custom Agent | Incident Commander agent | `.kiro/agents/incident-agent.json` |

A detailed index, including which test file backs each of the six correctness
properties, is in `docs/lesson-mapping.md`.

## Architecture

```
Frontend (React/TypeScript)          [optional/later]
    -> Backend API (FastAPI)
        -> Service layer (business rules)
            -> Repository layer (SQLite)
Diagnosis Agent
    -> MCP Server tools (logs, metrics, history, runbook)
    -> LLM Provider (Bedrock/Anthropic)   [injected; stubbed in tests]
```

Deterministic logic (ID generation, status state machine, timeline appends,
agent orchestration) is kept separate from the one non-deterministic boundary
(the LLM call), so the core is fully unit- and property-testable without a live
model. See `.kiro/steering/architecture.md`.

## Repository Layout

```
.kiro/
  specs/incident-management/   Lesson 1: requirements, design, tasks
  steering/                    Lesson 2: product, architecture, coding-standards, testing
  hooks/                       Lesson 3: lint/test hooks (+ Kironomics tracking)
  agents/                      Lesson 7: incident-agent.json
  settings/mcp.json            Lesson 6: MCP server registration
backend/                       Python (FastAPI) service, MCP tools, diagnosis agent, tests
mcp/incident-mcp/              Lesson 6: standalone connectable MCP server
powers/incident-analysis/      Lesson 5: Incident Analysis Power
docs/                          lesson-mapping.md and other docs
```

## Backend Setup

```
cd backend
py -m pip install -e ".[dev]"    # fastapi, uvicorn, pydantic, pytest, hypothesis, httpx
py -m pytest -q                  # run all tests (unit + property-based)
py -m uvicorn api.app:create_app --factory --reload   # run the API
```

Configuration is read from the environment (no secrets in source):
`KIROOPS_DB_PATH`, `KIROOPS_LLM_MODEL_ID`, `KIROOPS_LLM_ENDPOINT`.

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/incidents` | Create an incident (validates title/severity, assigns INC-####, status OPEN) |
| GET | `/incidents` | List incidents |
| GET | `/incidents/{id}` | Get an incident with its timeline |
| PATCH | `/incidents/{id}/status` | Advance status (OPEN -> INVESTIGATING -> RESOLVED) |
| POST | `/incidents/{id}/diagnosis` | Request an AI diagnosis (503 if the LLM is unavailable) |
| GET | `/incidents/{id}/remediation-actions` | List recommended remediation actions |

## Deploying to AWS (Lambda + API Gateway + DynamoDB)

KiroOps runs serverless in the cloud: an HTTP API Gateway fronts a single
Lambda function (the FastAPI app wrapped by Mangum), with **DynamoDB** as the
cloud persistence backend and **Amazon Bedrock Nova** powering live diagnosis.
Local development stays on SQLite, so nothing about the local workflow changes.

The AWS CDK v2 (Python) app lives in [`infra/`](infra/README.md). It is
infrastructure-as-code only and does not deploy automatically. See
[`infra/README.md`](infra/README.md) for prerequisites, install, `cdk synth`,
`cdk deploy`, and the required Bedrock model-access note.

## Status

Backend, MCP server, and diagnosis agent are complete with all six correctness
properties covered by passing property-based tests. The real Bedrock/Anthropic
LLM provider and the React frontend are optional later work; the core runs and
is fully tested with a stubbed model boundary.