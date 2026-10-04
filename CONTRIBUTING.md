# Contributing to KiroOps

Contributions are welcome. KiroOps follows a spec-driven, test-first workflow
(see the `.kiro/` folder and `docs/lesson-mapping.md`).

## Local setup

### Backend (Python 3.11+)

```
cd backend
python -m venv .venv
pip install -e ".[dev]"
pytest -q
```

To start the API locally, see the Backend Setup section of the main README.
Local development uses SQLite (`KIROOPS_PERSISTENCE` unset); the cloud
deployment uses DynamoDB (see `infra/README.md`).

### Frontend (Node 18+)

```
cd frontend
npm install
npm run build
npm run test
npm run typecheck
```

The Vite dev server command is in `frontend/README.md`.

## Workflow

1. Fork the repo and create a feature branch (for example feature/your-change).
2. Make focused commits with clear messages.
3. Add or update tests. New behavior needs at least one test; any invariant it
   touches should be covered by a property-based test (`backend/tests/*_property.py`).
4. Ensure the full suite passes: backend `pytest -q`; frontend tests and typecheck.
5. Open a pull request describing the change, what you tested, and any tradeoffs.

## Conventions

- Keep business logic in the service layer, not in API routes.
- Use typed interfaces at every boundary (Pydantic models, TypeScript types).
- Treat the LLM as the only non-deterministic boundary; keep it behind the
  injected provider so the core stays testable.
- The timeline is append-only; never add update or delete for timeline events.
- No hard-coded secrets, endpoints, or model ids - read them from configuration.
- Match the existing style; see `.kiro/steering/coding-standards.md`.

## Reporting issues

Open a GitHub issue with steps to reproduce, expected vs actual behavior, and
relevant logs or screenshots. For security-sensitive reports, do not post
secrets or tokens in the issue.