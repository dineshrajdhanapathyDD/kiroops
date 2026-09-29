/**
 * App shell (Task 13, composition).
 *
 * Minimal client-side view switching between the create, list, and detail
 * pages — no router dependency to keep the app lean. State here is limited to
 * which view is active and the selected incident id; all data-loading lives in
 * the page components via the services layer.
 */

import { useState } from "react";
import { CreateIncidentPage } from "./pages/CreateIncidentPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentListPage } from "./pages/IncidentListPage";

type View =
  | { name: "list" }
  | { name: "create" }
  | { name: "detail"; incidentId: string };

export function App(): JSX.Element {
  const [view, setView] = useState<View>({ name: "list" });
  const [reloadKey, setReloadKey] = useState(0);

  function refreshList(): void {
    setReloadKey((k) => k + 1);
  }

  return (
    <main>
      <header>
        <h1>KiroOps</h1>
        <nav aria-label="Primary">
          <button type="button" onClick={() => setView({ name: "list" })}>
            Incidents
          </button>
          <button type="button" onClick={() => setView({ name: "create" })}>
            New incident
          </button>
        </nav>
      </header>

      {view.name === "list" ? (
        <IncidentListPage
          reloadKey={reloadKey}
          onSelect={(incidentId) => setView({ name: "detail", incidentId })}
        />
      ) : null}

      {view.name === "create" ? (
        <CreateIncidentPage
          onCreated={(incident) => {
            refreshList();
            setView({ name: "detail", incidentId: incident.incidentId });
          }}
        />
      ) : null}

      {view.name === "detail" ? (
        <IncidentDetailPage
          incidentId={view.incidentId}
          onStatusChanged={refreshList}
        />
      ) : null}
    </main>
  );
}
