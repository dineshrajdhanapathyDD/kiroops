/**
 * IncidentListPage (Task 13.4, Req 2.1).
 *
 * Loads incidents through `incidentsApi.list()` and renders them in a table
 * (id, title, severity, service, status). Selecting a row asks the parent to
 * open the detail view. Presentational: no HTTP logic beyond the service call.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError, incidentsApi } from "../api/incidents";
import type { Incident } from "../types";

interface IncidentListPageProps {
  /** Called with the incident id when a row is opened. */
  onSelect?: (incidentId: string) => void;
  /**
   * Bump this value to force a reload (e.g. after creating an incident).
   */
  reloadKey?: number;
}

export function IncidentListPage({
  onSelect,
  reloadKey = 0,
}: IncidentListPageProps): JSX.Element {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setIncidents(await incidentsApi.list());
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load incidents.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  if (loading) {
    return <p>Loading incidentsâ€¦</p>;
  }
  if (error) {
    return <p role="alert">{error}</p>;
  }

  return (
    <section aria-labelledby="list-heading">
      <h2 id="list-heading">Incidents</h2>
      {incidents.length === 0 ? (
        <p>No incidents yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Title</th>
              <th scope="col">Severity</th>
              <th scope="col">Service</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((incident) => (
              <tr key={incident.incidentId}>
                <td>
                  <button
                    type="button"
                    onClick={() => onSelect?.(incident.incidentId)}
                  >
                    {incident.incidentId}
                  </button>
                </td>
                <td>{incident.title}</td>
                <td><span className={`badge sev-${incident.severity}`}>{incident.severity}</span></td>
                <td>{incident.service}</td>
                <td><span className={`badge status-${incident.status}`}>{incident.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
