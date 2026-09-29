# Runbook: Common Symptom -> Mitigation

A starter runbook mapping observed symptom patterns to likely causes and
mitigations. Pair this with `search_runbook` results for the affected service.

## High error rate (many ERROR logs, error_rate elevated)
- Likely: bad deploy, downstream dependency failing, or resource exhaustion.
- Mitigation: check recent deploys and roll back if the error rate rose right
  after one; verify downstream health; if connection errors dominate, see below.

## Elevated p95 latency (latency up, error rate moderate)
- Likely: downstream slowness, GC pauses, or a slow query.
- Mitigation: correlate latency with downstream calls and DB query times; add or
  tune indexes for slow queries; scale out if CPU-bound.

## Connection pool exhausted / database connection refused
- Likely: pool too small for load, or the database is unhealthy.
- Mitigation: increase connection pool size; verify DB health and max connections;
  add retry-with-backoff for transient failures.

## High CPU (cpu_pct high, latency up)
- Likely: hot code path, insufficient capacity, or a runaway loop.
- Mitigation: scale horizontally; profile CPU-bound paths; check for recent code
  changes that increased per-request work.

## High memory / OOM (memory_pct high, restarts)
- Likely: memory leak or undersized instances.
- Mitigation: inspect memory trends; restart leaking instances as a stopgap;
  raise limits or fix the leak.

## No clear signal
- If logs, metrics, and history do not converge, state that the diagnosis is
  inconclusive and recommend gathering more evidence rather than guessing.