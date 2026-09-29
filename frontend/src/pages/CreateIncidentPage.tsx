/**
 * CreateIncidentPage (Task 13.3, Req 1.6/1.7).
 *
 * Form with title, severity dropdown (LOW/MEDIUM/HIGH/CRITICAL), and service.
 * Client-side rejects an empty/whitespace title before submitting, and surfaces
 * server-side validation errors (422 with `field` = "title" | "severity") next
 * to the offending field. All HTTP goes through `incidentsApi`; this component
 * stays presentational.
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, incidentsApi } from "../api/incidents";
import type { Incident, Severity } from "../types";

const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

interface CreateIncidentPageProps {
  /** Called with the created incident so the parent can navigate/refresh. */
  onCreated?: (incident: Incident) => void;
}

export function CreateIncidentPage({
  onCreated,
}: CreateIncidentPageProps): JSX.Element {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<Severity>("LOW");
  const [service, setService] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Field-scoped and form-level errors.
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<string, string>>>(
    {},
  );
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setFieldErrors({});
    setFormError(null);

    // Client-side validation: reject empty/whitespace title before submit.
    if (title.trim() === "") {
      setFieldErrors({ title: "Title is required." });
      return;
    }

    setSubmitting(true);
    try {
      const incident = await incidentsApi.create({
        title: title.trim(),
        severity,
        service: service.trim(),
      });
      // Reset on success.
      setTitle("");
      setService("");
      setSeverity("LOW");
      onCreated?.(incident);
    } catch (err) {
      if (err instanceof ApiError) {
        // Surface server validation errors on the named field when present.
        if (err.field) {
          setFieldErrors({ [err.field]: err.message });
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby="create-heading">
      <h2 id="create-heading">Create incident</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="title">Title</label>
          <input
            id="title"
            name="title"
            type="text"
            value={title}
            aria-invalid={fieldErrors.title ? true : undefined}
            aria-describedby={fieldErrors.title ? "title-error" : undefined}
            onChange={(e) => setTitle(e.target.value)}
          />
          {fieldErrors.title ? (
            <p id="title-error" role="alert">
              {fieldErrors.title}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="severity">Severity</label>
          <select
            id="severity"
            name="severity"
            value={severity}
            aria-invalid={fieldErrors.severity ? true : undefined}
            aria-describedby={
              fieldErrors.severity ? "severity-error" : undefined
            }
            onChange={(e) => setSeverity(e.target.value as Severity)}
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {fieldErrors.severity ? (
            <p id="severity-error" role="alert">
              {fieldErrors.severity}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="service">Service</label>
          <input
            id="service"
            name="service"
            type="text"
            value={service}
            onChange={(e) => setService(e.target.value)}
          />
        </div>

        {formError ? <p role="alert">{formError}</p> : null}

        <button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create incident"}
        </button>
      </form>
    </section>
  );
}
