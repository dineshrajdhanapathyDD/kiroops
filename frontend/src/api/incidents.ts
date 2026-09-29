/**
 * Services layer for the KiroOps backend (Task 13.2).
 *
 * Responsibilities (per coding-standards.md "TypeScript / React"):
 *  - Centralize every HTTP call to the FastAPI backend.
 *  - Read the base URL from configuration (`VITE_API_BASE_URL`, localhost default).
 *  - Adapt the snake_case wire shape into the camelCase types in `types.ts`.
 *  - Map the shared error envelope `{ error: { code, message, field? } }` into a
 *    thrown, typed `ApiError` so presentational components can render messages
 *    without knowing the transport.
 *
 * Endpoints (design.md):
 *  POST   /incidents                          -> 201 IncidentResponse
 *  GET    /incidents                          -> 200 IncidentSummary[]
 *  GET    /incidents/{id}                      -> 200 IncidentDetailResponse
 *  PATCH  /incidents/{id}/status               -> 200 IncidentResponse
 *  POST   /incidents/{id}/diagnosis            -> 200 DiagnosisResponse (503 unavailable)
 *  GET    /incidents/{id}/remediation-actions  -> 200 RemediationActionModel[]
 */

import type {
  Diagnosis,
  Incident,
  IncidentDetail,
  IncidentStatus,
  RemediationAction,
  Severity,
  TimelineEvent,
} from "../types";

/** Base URL of the backend; falls back to localhost for local dev. */
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

/**
 * Typed error carrying the backend envelope fields. Components can switch on
 * `code` or show `message`, and use `field` to highlight a specific input.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly field: string | undefined;
  readonly httpStatus: number;

  constructor(
    code: string,
    message: string,
    httpStatus: number,
    field?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.httpStatus = httpStatus;
    this.field = field;
  }
}

// --- Wire shapes (snake_case, exactly as the backend serializes them) --------

interface IncidentWire {
  incident_id: string;
  title: string;
  severity: Severity;
  service: string;
  status: IncidentStatus;
  created_at: string;
}

interface TimelineEventWire {
  type: TimelineEvent["type"];
  timestamp: string;
  details: Record<string, unknown>;
}

interface IncidentDetailWire extends IncidentWire {
  timeline: TimelineEventWire[];
}

interface RemediationActionWire {
  action_id: string;
  description: string;
  rationale: string;
}

interface DiagnosisWire {
  incident_id: string;
  summary: string;
  evidence_refs: string[];
  remediation_actions: RemediationActionWire[];
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; field?: string };
}

// --- Adapters: wire (snake_case) -> app types (camelCase) --------------------

function toIncident(w: IncidentWire): Incident {
  return {
    incidentId: w.incident_id,
    title: w.title,
    severity: w.severity,
    service: w.service,
    status: w.status,
    createdAt: w.created_at,
  };
}

function toTimelineEvent(w: TimelineEventWire): TimelineEvent {
  return { type: w.type, timestamp: w.timestamp, details: w.details };
}

function toIncidentDetail(w: IncidentDetailWire): IncidentDetail {
  return {
    ...toIncident(w),
    timeline: w.timeline.map(toTimelineEvent),
  };
}

function toRemediationAction(w: RemediationActionWire): RemediationAction {
  return {
    actionId: w.action_id,
    description: w.description,
    rationale: w.rationale,
  };
}

function toDiagnosis(w: DiagnosisWire): Diagnosis {
  return {
    incidentId: w.incident_id,
    summary: w.summary,
    evidenceRefs: w.evidence_refs,
    remediationActions: w.remediation_actions.map(toRemediationAction),
  };
}

// --- Core fetch helper -------------------------------------------------------

interface RequestOptions {
  method?: string;
  body?: unknown;
}

/**
 * Perform a JSON request and return the parsed body, or throw `ApiError`.
 *
 * On a non-2xx response the shared envelope is parsed into an `ApiError`. When
 * the body is missing or malformed, a generic `ApiError` is synthesized from the
 * HTTP status so callers always get a typed failure.
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body } = options;

  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    // Network-level failure (server down, CORS, offline).
    throw new ApiError(
      "network_error",
      "Unable to reach the server. Check that the backend is running.",
      0,
      undefined,
    );
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  // 204 or empty body: nothing to parse.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function parseError(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope | undefined;
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = undefined;
  }
  const err = envelope?.error;
  const code = err?.code ?? `http_${response.status}`;
  const message =
    err?.message ?? `Request failed with status ${response.status}.`;
  return new ApiError(code, message, response.status, err?.field);
}

// --- Public API --------------------------------------------------------------

export interface CreateIncidentInput {
  title: string;
  severity: Severity;
  service: string;
}

export const incidentsApi = {
  async create(req: CreateIncidentInput): Promise<Incident> {
    const wire = await request<IncidentWire>("/incidents", {
      method: "POST",
      body: req,
    });
    return toIncident(wire);
  },

  async list(): Promise<Incident[]> {
    const wire = await request<IncidentWire[]>("/incidents");
    return wire.map(toIncident);
  },

  async get(id: string): Promise<IncidentDetail> {
    const wire = await request<IncidentDetailWire>(
      `/incidents/${encodeURIComponent(id)}`,
    );
    return toIncidentDetail(wire);
  },

  async updateStatus(id: string, status: IncidentStatus): Promise<Incident> {
    const wire = await request<IncidentWire>(
      `/incidents/${encodeURIComponent(id)}/status`,
      { method: "PATCH", body: { status } },
    );
    return toIncident(wire);
  },

  async requestDiagnosis(id: string): Promise<Diagnosis> {
    const wire = await request<DiagnosisWire>(
      `/incidents/${encodeURIComponent(id)}/diagnosis`,
      { method: "POST" },
    );
    return toDiagnosis(wire);
  },

  async getRemediationActions(id: string): Promise<RemediationAction[]> {
    const wire = await request<RemediationActionWire[]>(
      `/incidents/${encodeURIComponent(id)}/remediation-actions`,
    );
    return wire.map(toRemediationAction);
  },
};

export type IncidentsApi = typeof incidentsApi;
