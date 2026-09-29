# KiroOps Frontend

A Vite + React + TypeScript (strict) client for the KiroOps incident-management
backend. It provides three views — create an incident, list incidents, and an
incident detail page with timeline, AI diagnosis, and status controls.

## Prerequisites

- Node.js 18+ (developed against Node 22)
- The KiroOps FastAPI backend running (see `../backend`)

## Setup

```bash
npm install
```

## Configuration

The base URL of the backend is read from `VITE_API_BASE_URL`. When unset, the
services layer falls back to `http://localhost:8000`.

Create a `.env.local` (or `.env`) from the example:

```bash
cp .env.example .env.local
# then edit VITE_API_BASE_URL if your backend runs elsewhere
```

## Scripts

```bash
npm run dev        # start the Vite dev server (default http://localhost:5173)
npm run build      # type-check (tsc -b) and build for production into dist/
npm run preview    # preview the production build
npm run typecheck  # strict type-check only, no emit
npm run test       # run the component tests once (vitest run)
npm run test:watch # run tests in watch mode
```

## Architecture

- `src/types.ts` — shared domain types mirroring the backend response models.
  Types are camelCase per the TS coding standard; the backend serializes
  snake_case (`incident_id`, `created_at`, ...). The snake_case → camelCase
  adaptation happens once, in the services layer, so components only ever see
  camelCase.
- `src/api/incidents.ts` — the services layer. All HTTP lives here. It centralizes
  fetch calls, reads `VITE_API_BASE_URL`, adapts wire shapes to the shared types,
  and maps the backend error envelope `{ error: { code, message, field? } }` into
  a thrown, typed `ApiError` so components can render messages.
- `src/statusMachine.ts` — client mirror of the backend status state machine used
  to offer only valid next states (OPEN → INVESTIGATING → RESOLVED). The backend
  remains the sole authority and still rejects invalid transitions with 409.
- `src/pages/` — presentational pages: `CreateIncidentPage`, `IncidentListPage`,
  `IncidentDetailPage`.
- `src/App.tsx` — minimal client-side view switching (no router dependency).
- `src/__tests__/` — component tests (Vitest + Testing Library) that mock the
  services layer so no network is hit.

## Backend contract

| Method | Path | Response |
|--------|------|----------|
| POST   | `/incidents` | `201` incident |
| GET    | `/incidents` | `200` incident summaries |
| GET    | `/incidents/{id}` | `200` incident + timeline |
| PATCH  | `/incidents/{id}/status` | `200` incident |
| POST   | `/incidents/{id}/diagnosis` | `200` diagnosis (`503` when unavailable) |
| GET    | `/incidents/{id}/remediation-actions` | `200` remediation actions |

Errors use the envelope `{ "error": { "code", "message", "field"? } }` with
`422` (validation), `404` (unknown id), `409` (invalid transition), and `503`
(diagnosis unavailable).
