# KiroOps Demo Script (3 minutes)

A timed walkthrough for the Kiro University submission video. The goal is that a
reviewer can see the project working AND find each of the seven lessons without
guessing. Times are targets, not hard cuts. Keep narration tight.

Setup before recording:
- Backend running:  `cd backend; py -m uvicorn api.app:create_app --factory --reload`
- Frontend running: `cd frontend; npm run dev`  (uses VITE_API_BASE_URL, default http://localhost:8000)
- Have the GitHub repo tab open: https://github.com/dineshrajdhanapathyDD/kiroops
- Have the Kiro IDE open on the project so .kiro/ is visible.

---

## 0:00 - 0:20  Intro + the app
Say: "This is KiroOps, an AI incident investigation platform. A developer files
an incident, and KiroOps gathers evidence and produces an AI diagnosis."
Show: the KiroOps dashboard (incident list page).

## 0:20 - 0:40  Create an incident  (product flow)
Do: open Create Incident, enter title "Production API returning 500 errors",
service "checkout", severity HIGH, submit.
Show: the new incident appears with an INC-#### id and status OPEN.
Say: "Every incident gets a unique ID and starts OPEN."

## 0:40 - 1:00  AI diagnosis + the custom agent  (Lesson 7)
Do: open the incident, click "Request Diagnosis".
Show: the diagnosis summary, evidence references, and remediation actions.
Say: "The Incident Commander agent gathers evidence and produces an
evidence-based diagnosis. Its config lives in .kiro/agents/incident-agent.json."
Show (briefly): .kiro/agents/incident-agent.json in the IDE.

## 1:00 - 1:20  MCP  (Lesson 6)  [1000-credit lesson - dwell here]
Say: "The evidence comes through a custom MCP server exposing four tools:
recent logs, service metrics, incident history, and runbook search."
Show: mcp/incident-mcp/server.py and .kiro/settings/mcp.json (the four tools in
autoApprove). Mention data is simulated and seeded per service.

## 1:20 - 1:35  Powers  (Lesson 5)
Say: "I packaged the investigation workflow as a Kiro Power."
Show: powers/incident-analysis/ - plugin.json, skills/incident-analysis/SKILL.md,
and references/ (severity.md, runbook.md).

## 1:35 - 1:50  Steering  (Lesson 2)
Say: "Persistent project guidance lives in steering files that Kiro applies to
every interaction."
Show: .kiro/steering/ - product.md, architecture.md, coding-standards.md,
testing.md.

## 1:50 - 2:05  Hooks  (Lesson 3)
Say: "Hooks automate lint and tests on save."
Show: .kiro/hooks/lint-on-save.json and test-on-change.json. Optionally save a
backend .py file and show the test hook firing.

## 2:05 - 2:20  Property-based testing  (Lesson 4)
Do: `cd backend; py -m pytest -q`
Show: the suite passing. Point out the *_property.py files.
Say: "Six correctness properties - like 'incident IDs are unique and monotonic'
and 'status transitions follow the state machine' - are checked with Hypothesis,
100+ generated cases each."

## 2:20 - 2:40  Spec-driven development  (Lesson 1)
Show: .kiro/specs/incident-management/ - requirements.md, design.md, tasks.md.
Say: "I started from a spec: EARS requirements, a design with a correctness-
properties section, then a task list. The code was built task by task from it."

## 2:40 - 3:00  GitHub .kiro folder + wrap-up
Show: the GitHub repo, the README lesson matrix, and the .kiro/ folder in the
public repo.
Say: "Everything is in the public repo. The README maps all seven lessons to
their exact paths. That's KiroOps - spec-driven, steered, hooked, property-
tested, powered, MCP-backed, and agent-driven."

---

## Lesson-to-evidence quick reference (for the reviewer)

| Lesson | On screen at | Path |
|--------|--------------|------|
| 1 Spec | 2:20 | .kiro/specs/incident-management/ |
| 2 Steering | 1:35 | .kiro/steering/ |
| 3 Hooks | 1:50 | .kiro/hooks/ |
| 4 PBT | 2:05 | backend/tests/*_property.py |
| 5 Powers | 1:20 | powers/incident-analysis/ |
| 6 MCP | 1:00 | mcp/incident-mcp/ + .kiro/settings/mcp.json |
| 7 Agent | 0:40 | .kiro/agents/incident-agent.json |

## Tips
- If the live LLM provider is not configured, the diagnosis endpoint returns 503
  by design (graceful degradation). For the video, either wire the real provider
  (optional task 12) or narrate the flow using the tested stubbed path.
- Keep each lesson on screen at least 3-4 seconds so a reviewer can read the path.
- Record at 1080p; zoom the editor font so file paths are legible.