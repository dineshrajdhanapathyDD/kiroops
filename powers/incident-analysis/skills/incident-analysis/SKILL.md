# Incident Analysis

Use this skill when investigating an operational incident in KiroOps or any
service-oriented system. It provides a repeatable workflow for turning raw
symptoms into an evidence-based diagnosis and concrete remediation actions.

## When to use

- A developer reports an incident (e.g. "Production API returning 500 errors").
- You are asked to diagnose, triage, or recommend remediation for a service.
- You are working on KiroOps incident-management tasks.

## Workflow

```
Incident
   -> Classify severity        (references/severity.md)
   -> Gather evidence          (incident-mcp tools)
   -> Analyze symptoms         (correlate logs + metrics + history)
   -> Check runbook            (references/runbook.md, search_runbook)
   -> Produce investigation    (diagnosis + evidence refs)
   -> Recommend remediation    (actions with rationale)
```

### 1. Classify severity
Determine LOW / MEDIUM / HIGH / CRITICAL using `references/severity.md`. Severity
sets urgency and how much evidence to gather before acting.

### 2. Gather evidence (MCP)
Call all four incident-mcp tools for the incident's service before concluding:
- `get_recent_logs(service, limit)` - recent INFO/WARN/ERROR entries
- `get_service_metrics(service, window_minutes)` - error_rate, p95_latency_ms, cpu_pct, memory_pct
- `get_incident_history(service, limit)` - previously resolved incidents
- `search_runbook(service, query)` - matching runbook entries

### 3. Analyze symptoms
Correlate the evidence:
- Does `error_rate` track the volume of ERROR log entries?
- Is `p95_latency_ms` elevated alongside `cpu_pct` / `memory_pct`?
- Has a similar incident happened before (history)? What resolved it?

### 4. Check the runbook
Use `references/runbook.md` and `search_runbook` results to find a known
mitigation for the observed symptom pattern.

### 5. Produce the diagnosis
Write a concise summary of the most likely root cause. Every claim must cite the
evidence it rests on. If evidence is inconclusive, say so - do not guess.

### 6. Recommend remediation
Derive actions from the diagnosis and any matching runbook. Each action has a
short description and a rationale tied to the evidence.

## Rules

- Evidence first. No claim without a supporting reference.
- Read-only with respect to incident status: analysis never changes state.
- If tools or the model are unavailable, report diagnosis-unavailable rather
  than fabricating a cause.

## References

- `references/severity.md` - severity classification guide
- `references/runbook.md` - common symptom -> mitigation runbook