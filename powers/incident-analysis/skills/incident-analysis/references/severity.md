# Severity Classification

Classify every incident into one of four levels. Severity drives urgency and how
much evidence to gather before acting.

| Severity | Meaning | Typical signals | Response |
|----------|---------|-----------------|----------|
| CRITICAL | Widespread outage or data loss; core flow down | error_rate very high, p95 latency spiking, checkout/auth down | Investigate immediately; gather all evidence; page on-call |
| HIGH | Major feature degraded for many users | elevated error_rate, latency well above baseline, repeated ERROR logs | Investigate promptly; full evidence gather |
| MEDIUM | Partial or intermittent degradation | some ERROR/WARN logs, mild latency or resource pressure | Investigate during business hours; targeted evidence |
| LOW | Minor or cosmetic; little user impact | isolated WARN logs, metrics near baseline | Track; batch with other work |

## How to decide

1. Start from user impact (scope x severity of effect), not from the raw metric.
2. Use `get_service_metrics` to confirm: a CRITICAL claim should be backed by a
   high `error_rate` and/or a large `p95_latency_ms` increase.
3. Cross-check `get_recent_logs`: a burst of ERROR entries supports HIGH/CRITICAL.
4. If signals disagree (e.g. high latency but low error rate), pick the level the
   evidence supports and note the ambiguity in the diagnosis.

## Notes

- Severity is provided at incident creation but can be re-assessed once evidence
  is gathered. If the evidence contradicts the reported severity, say so.
- Do not inflate severity without evidence; do not downplay a CRITICAL signal.