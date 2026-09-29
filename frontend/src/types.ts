/**
 * Shared domain types for the KiroOps frontend (Task 13.1).
 *
 * These mirror the backend response models in `design.md` / `backend/api/models.py`.
 *
 * Wire-format vs. TS convention
 * -----------------------------
 * The backend serializes fields in snake_case (`incident_id`, `created_at`,
 * `evidence_refs`, `remediation_actions`, `action_id`). This module defines the
 * app-facing types in camelCase per the frontend coding standard
 * (PascalCase types, camelCase fields). The adaptation from the snake_case wire
 * shape to these camelCase types happens exactly once, in the services layer
 * (`api/incidents.ts`). Components only ever see these camelCase types, so no
 * snake_case leaks past the boundary.
 *
 * Enum string values below are the exact wire values the backend emits, so the
 * unions double as a compile-time check that the frontend and backend agree.
 */

/** Incident severity. Wire values match `backend.domain.models.Severity`. */
export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

/** Incident lifecycle status. Wire values match `IncidentStatus`. */
export type IncidentStatus = "OPEN" | "INVESTIGATING" | "RESOLVED";

/**
 * Timeline event type. Wire values are the human-readable strings the backend
 * emits (note the spaces), not enum identifiers.
 */
export type TimelineEventType =
  | "created"
  | "status changed"
  | "diagnosis requested"
  | "actions suggested";

/** A single entry on an incident's append-only timeline. */
export interface TimelineEvent {
  type: TimelineEventType;
  /** ISO-8601 timestamp. */
  timestamp: string;
  /** Structured payload, e.g. `{ from: "OPEN", to: "INVESTIGATING" }`. */
  details: Record<string, unknown>;
}

/** Core incident record (list + create + status-update responses). */
export interface Incident {
  incidentId: string;
  title: string;
  severity: Severity;
  service: string;
  status: IncidentStatus;
  /** ISO-8601 timestamp. */
  createdAt: string;
}

/** Incident plus its full timeline (GET /incidents/{id}). */
export interface IncidentDetail extends Incident {
  /** Ordered earliest -> latest by the backend. */
  timeline: TimelineEvent[];
}

/** A recommended corrective step derived from a diagnosis. */
export interface RemediationAction {
  actionId: string;
  description: string;
  rationale: string;
}

/** Result of an AI diagnosis request (POST /incidents/{id}/diagnosis). */
export interface Diagnosis {
  incidentId: string;
  summary: string;
  evidenceRefs: string[];
  remediationActions: RemediationAction[];
}
