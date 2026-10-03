# KiroOps Walkthrough

A visual, step-by-step walkthrough of KiroOps running live on AWS. Each step
maps to the Kiro University lessons the project demonstrates. Screenshots live
in `docs/screenshots/`.

Live demo:
- Frontend (CloudFront): https://d2k4ginzxvtoqs.cloudfront.net
- API (API Gateway): https://9gjx9zin9g.execute-api.us-east-1.amazonaws.com

Serverless architecture (us-east-1): CloudFront + S3 (React SPA) -> API Gateway
-> AWS Lambda (FastAPI via Mangum, Graviton) -> DynamoDB, with Amazon Bedrock
Nova powering AI diagnosis. Infrastructure as code lives in `infra/` (AWS CDK).

---

## Step 1 - Incident dashboard

The landing view lists all incidents from DynamoDB: ID, title, severity, and
status, with color-coded badges. This is the operator's starting point.

![Incident list](screenshots/01-incident-list.png)

/ Lessons in play: the whole stack is spec-driven (Lesson 1) and guided by
steering files (Lesson 2). /

---

## Step 2 - Create an incident

The operator files a new incident (title, severity, affected service). The form
validates a non-empty title client-side and surfaces server validation errors
(422) on the offending field. On submit the backend assigns a unique
`INC-####` id and sets status `OPEN`.

![Create incident](screenshots/02-create-incident.png)

/ The ID format and validation are covered by property-based tests (Lesson 4):
IDs are non-empty, unique, and monotonic. /

---

## Step 3 - Incident detail and timeline

Opening an incident shows its current status, an append-only timeline of events
(created, status changed, diagnosis requested, actions suggested), and
status-advance controls that only offer valid next states
(OPEN -> INVESTIGATING -> RESOLVED).

![Incident detail](screenshots/03-incident-detail.png)

/ The status state machine and append-only timeline are each backed by
property-based tests (Lesson 4). /

---

## Step 4 - AI diagnosis (Amazon Bedrock Nova)

Clicking "Request Diagnosis" runs the Incident Commander agent: it gathers
evidence through the custom MCP server (recent logs, service metrics, incident
history, runbook search), calls Amazon Bedrock Nova, and returns an
evidence-based diagnosis plus recommended remediation actions. The evidence
references and remediation cards are shown, and the events are appended to the
timeline.

![AI diagnosis](screenshots/04-ai-diagnosis.png)

/ Lessons in play: MCP server (Lesson 6) feeds the custom agent (Lesson 7). If
the model is unavailable the endpoint returns 503 by design (graceful
degradation), a behavior covered by a property-based test (Lesson 4). /

---

## Step 5 - Public GitHub repository

The project is a public repo. The README leads with a lesson matrix mapping each
of the seven Kiro University lessons to its exact path in the codebase.

![GitHub repository](screenshots/05-github-repo.png)

---

## Step 6 - The .kiro configuration folder

The `.kiro/` folder is the heart of the submission: it holds the spec, steering
files, hooks, the custom agent config, and the MCP server registration - the
evidence for Lessons 1, 2, 3, 6, and 7.

![.kiro folder](screenshots/06-kiro-folder.png)

---

## Lesson-to-step map

| Lesson | Where it shows | Evidence path |
|--------|----------------|---------------|
| 1. Spec-driven development | Steps 1-6 (whole app) | `.kiro/specs/incident-management/` |
| 2. Steering | Guides all behavior | `.kiro/steering/` |
| 3. Hooks | lint/test automation | `.kiro/hooks/` |
| 4. Property-based testing | Steps 2, 3, 4 | `backend/tests/*_property.py` |
| 5. Powers | Incident Analysis Power | `powers/incident-analysis/` |
| 6. MCP | Step 4 (evidence gathering) | `mcp/incident-mcp/` + `.kiro/settings/mcp.json` |
| 7. Custom Agent | Step 4 (diagnosis) | `.kiro/agents/incident-agent.json` |

See `docs/lesson-mapping.md` for the detailed index and `docs/demo-script.md`
for the timed video walkthrough.

---

## How to reproduce the screenshots

1. Deploy (or use the live URLs above).
2. Open the frontend, which shows the incident list (Step 1).
3. Click "New incident", fill the form (Step 2).
4. Open an incident to see status + timeline (Step 3).
5. Click "Request Diagnosis" to get the live Nova diagnosis (Step 4).
6. Visit the GitHub repo (Step 5) and its `.kiro/` folder (Step 6).