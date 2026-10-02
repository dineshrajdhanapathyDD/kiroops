/**
 * IncidentDetailPage (Task 13.5, Req 2.2/2.4/5.4).
 *
 * Shows the current status, the timeline in chronological order (as returned by
 * the backend), a "Request Diagnosis" action, the resulting diagnosis and its
 * remediation actions, and status-advance controls that only offer valid next
 * states (OPEN -> INVESTIGATING -> RESOLVED).
 *
 * All HTTP goes through `incidentsApi`. The component keeps local UI state
 * (loading/error/diagnosis) but no transport logic.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError, incidentsApi } from "../api/incidents";
import { nextStates } from "../statusMachine";
import type {
  Diagnosis,
  IncidentDetail,
  IncidentStatus,
  TimelineEvent,
} from "../types";

interface IncidentDetailPageProps {
  incidentId: string;
  /** Called after a successful status change so a parent list can refresh. */
  onStatusChanged?: () => void;
}

function formatDetails(details: Record<string, unknown>): string {
  const keys = Object.keys(details);
  if (keys.length === 0) {
    return "";
  }
  return keys.map((k) => `${k}: ${String(details[k])}`).join(", ");
}

function TimelineList({ events }: { events: TimelineEvent[] }): JSX.Element {
  if (events.length === 0) {
    return <p>No timeline events.</p>;
  }
  return (
    <ol aria-label="Timeline">
      {events.map((event, index) => (
        <li key={`${event.timestamp}-${index}`}>
          <span data-testid="timeline-type">{event.type}</span>
          {" â€” "}
          <time dateTime={event.timestamp}>{event.timestamp}</time>
          {formatDetails(event.details) ? (
            <> ({formatDetails(event.details)})</>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function DiagnosisView({ diagnosis }: { diagnosis: Diagnosis }): JSX.Element {
  return (
    <section aria-labelledby="diagnosis-heading">
      <h3 id="diagnosis-heading">Diagnosis</h3>
      <p>{diagnosis.summary}</p>

      {diagnosis.evidenceRefs.length > 0 ? (
        <>
          <h4>Evidence</h4>
          <ul>
            {diagnosis.evidenceRefs.map((ref) => (
              <li key={ref}>{ref}</li>
            ))}
          </ul>
        </>
      ) : null}

      <h4>Remediation actions</h4>
      {diagnosis.remediationActions.length === 0 ? (
        <p>No remediation actions suggested.</p>
      ) : (
        <ul aria-label="Remediation actions">
          {diagnosis.remediationActions.map((action) => (
            <li key={action.actionId} data-testid="remediation-action">
              <strong>{action.description}</strong>
              <div>{action.rationale}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function IncidentDetailPage({
  incidentId,
  onStatusChanged,
}: IncidentDetailPageProps): JSX.Element {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);

  const [statusError, setStatusError] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await incidentsApi.get(incidentId));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load incident.",
      );
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRequestDiagnosis(): Promise<void> {
    setDiagnosing(true);
    setDiagnosisError(null);
    try {
      setDiagnosis(await incidentsApi.requestDiagnosis(incidentId));
      // Timeline gains "diagnosis requested"/"actions suggested" events.
      await load();
    } catch (err) {
      setDiagnosisError(
        err instanceof ApiError
          ? err.message
          : "Diagnosis is currently unavailable.",
      );
    } finally {
      setDiagnosing(false);
    }
  }

  async function handleAdvanceStatus(target: IncidentStatus): Promise<void> {
    setUpdatingStatus(true);
    setStatusError(null);
    try {
      await incidentsApi.updateStatus(incidentId, target);
      await load();
      onStatusChanged?.();
    } catch (err) {
      setStatusError(
        err instanceof ApiError ? err.message : "Failed to update status.",
      );
    } finally {
      setUpdatingStatus(false);
    }
  }

  if (loading) {
    return <p>Loading incidentâ€¦</p>;
  }
  if (error) {
    return <p role="alert">{error}</p>;
  }
  if (!detail) {
    return <p role="alert">Incident not found.</p>;
  }

  const transitions = nextStates(detail.status);

  return (
    <section aria-labelledby="detail-heading">
      <h2 id="detail-heading">
        {detail.incidentId}: {detail.title}
      </h2>

      <dl>
        <dt>Status</dt>
        <dd data-testid="current-status"><span className={`badge status-${detail.status}`}>{detail.status}</span></dd>
        <dt>Severity</dt>
        <dd>{detail.severity}</dd>
        <dt>Service</dt>
        <dd>{detail.service}</dd>
        <dt>Created</dt>
        <dd>
          <time dateTime={detail.createdAt}>{detail.createdAt}</time>
        </dd>
      </dl>

      <section aria-labelledby="status-controls-heading">
        <h3 id="status-controls-heading">Advance status</h3>
        {transitions.length === 0 ? (
          <p>No further transitions available.</p>
        ) : (
          transitions.map((target) => (
            <button
              key={target}
              type="button"
              disabled={updatingStatus}
              onClick={() => handleAdvanceStatus(target)}
            >
              Move to {target}
            </button>
          ))
        )}
        {statusError ? <p role="alert">{statusError}</p> : null}
      </section>

      <section aria-labelledby="timeline-heading">
        <h3 id="timeline-heading">Timeline</h3>
        <TimelineList events={detail.timeline} />
      </section>

      <section aria-labelledby="diagnosis-controls-heading">
        <h3 id="diagnosis-controls-heading">AI diagnosis</h3>
        <button
          type="button"
          disabled={diagnosing}
          onClick={handleRequestDiagnosis}
        >
          {diagnosing ? "Requestingâ€¦" : "Request Diagnosis"}
        </button>
        {diagnosisError ? <p role="alert">{diagnosisError}</p> : null}
        {diagnosis ? <DiagnosisView diagnosis={diagnosis} /> : null}
      </section>
    </section>
  );
}
