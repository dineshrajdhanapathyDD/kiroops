# Product

## What KiroOps Is

KiroOps is an AI-powered incident investigation platform for developers. A
developer submits an operational incident (title, service, description,
severity). KiroOps tracks the incident through its lifecycle, gathers evidence
through a custom MCP server, produces an AI diagnosis, suggests remediation
actions, and maintains an append-only incident timeline.

This project is built for the Kiro University challenge and is designed to
demonstrate all seven Kiro University lessons as real parts of the development
workflow, not bolted on afterward.

## Core User Flow

1. Developer creates an incident (title, service, severity).
2. System assigns a unique incident ID (INC-####) and sets status OPEN.
3. Developer advances the incident through valid states:
   OPEN -> INVESTIGATING -> RESOLVED.
4. Developer requests an AI diagnosis. The Diagnosis Agent gathers evidence
   via MCP tools (logs, metrics, history, runbook) and calls an LLM.
5. System presents an evidence-based diagnosis and recommended remediation
   actions.
6. Every step is recorded on the incident timeline.

## Product Principles

- Evidence first: a diagnosis must reference the evidence it was built from.
- Auditability: the timeline is append-only. History is never rewritten.
- Safe state: invalid status transitions are rejected, never silently applied.
- Graceful degradation: when the LLM is unavailable, the system reports
  diagnosis-unavailable and leaves incident state untouched.
- Reviewable by design: specs, steering, and tests make intent explicit.

## Non-Goals

- Not a full production observability suite. MCP tools return simulated data.
- Not multi-tenant or access-controlled in this iteration.
- No incident deletion. Incidents and their timelines persist.