# Requirements Document

## Introduction

KiroOps incident-management is a feature for creating, tracking, and resolving operational incidents, augmented by an AI diagnosis agent. Operators create incidents with a title, severity, and affected service. Each incident progresses through a constrained lifecycle (OPEN -> INVESTIGATING -> RESOLVED) and maintains an append-only timeline of events. Operators can request an AI-generated, evidence-based diagnosis: an agent gathers evidence through a custom MCP server (recent logs, service metrics, incident history, runbook search) and calls a real large language model to produce a diagnosis and recommended remediation actions.

The backend is a Python (FastAPI-style) service persisting to local SQLite through a repository layer. The frontend is a TypeScript/React application. The MCP server exposes evidence-gathering tools returning simulated realistic data. The LLM integration (Bedrock/Anthropic) is treated as a non-deterministic external boundary with configurable model and endpoint, and graceful handling when unavailable.

This document defines the testable requirements. Two properties are called out explicitly to back later property-based tests: incident ID format/uniqueness and the status transition state machine.

## Glossary

- **KiroOps**: The overall incident-management system comprising the Backend_Service, MCP_Server, Diagnosis_Agent, and Frontend_App.
- **Backend_Service**: The Python (FastAPI-style) service that exposes the incident-management API and persists data through the Repository_Layer.
- **Repository_Layer**: The persistence abstraction over local SQLite used by the Backend_Service to store and retrieve incidents and timeline events.
- **Frontend_App**: The TypeScript/React client used by operators to create, view, and update incidents.
- **MCP_Server**: The custom Model Context Protocol server exposing evidence-gathering tools: get_recent_logs, get_service_metrics, get_incident_history, search_runbook. Tools return mocked/simulated realistic data.
- **Diagnosis_Agent**: The component that gathers evidence via the MCP_Server tools and calls the LLM_Provider to produce a diagnosis and remediation actions.
- **LLM_Provider**: The real large language model integration (Bedrock/Anthropic), a non-deterministic external boundary configured by model identifier and endpoint.
- **Incident**: A record representing an operational issue, with an Incident_ID, title, Severity, service, Incident_Status, and a Timeline.
- **Incident_ID**: A unique, non-empty identifier for an Incident, formatted as `INC-` followed by four or more zero-padded decimal digits, matching the pattern `INC-\d{4,}` (e.g. INC-0001).
- **Incident_Status**: The lifecycle state of an Incident, one of OPEN, INVESTIGATING, RESOLVED.
- **Severity**: The impact level provided at creation, one of LOW, MEDIUM, HIGH, CRITICAL.
- **Timeline**: The append-only, time-ordered log of Timeline_Events for an Incident.
- **Timeline_Event**: A single recorded occurrence in a Timeline, one of "created", "status changed", "diagnosis requested", "actions suggested", each with a timestamp.
- **Diagnosis**: The evidence-based analysis produced by the Diagnosis_Agent for an Incident.
- **Remediation_Action**: A recommended corrective step derived from a Diagnosis.
- **Valid_Transition**: A forward-adjacent Incident_Status change: OPEN -> INVESTIGATING or INVESTIGATING -> RESOLVED.

## Requirements

### Requirement 1: Create Incident

**User Story:** As an operator, I want to create an incident with a title, severity, and service, so that operational issues are tracked from the moment they are reported.

#### Acceptance Criteria

1. WHEN an operator submits a create-incident request with a non-empty title, a Severity of LOW, MEDIUM, HIGH, or CRITICAL, and a service, THE Backend_Service SHALL create an Incident and persist it through the Repository_Layer.
2. WHEN an Incident is created, THE Backend_Service SHALL assign an Incident_ID that is non-empty, unique across all Incidents, and matches the pattern `INC-\d{4,}`.
3. WHEN an Incident is created, THE Backend_Service SHALL assign sequential Incident_IDs such that each new Incident_ID has a numeric portion greater than every previously assigned Incident_ID numeric portion.
4. WHEN an Incident is created, THE Backend_Service SHALL set the initial Incident_Status to OPEN.
5. WHEN an Incident is created, THE Backend_Service SHALL append a "created" Timeline_Event with a timestamp to the Incident Timeline.
6. IF a create-incident request has an empty or whitespace-only title, THEN THE Backend_Service SHALL reject the request and return a validation error identifying the title field.
7. IF a create-incident request has a Severity that is not one of LOW, MEDIUM, HIGH, or CRITICAL, THEN THE Backend_Service SHALL reject the request and return a validation error identifying the Severity field.

### Requirement 2: View Incidents

**User Story:** As an operator, I want to list incidents and view a single incident with its status and timeline, so that I can understand the current operational state.

#### Acceptance Criteria

1. WHEN an operator requests the incident list, THE Backend_Service SHALL return all persisted Incidents, each including its Incident_ID, title, Severity, service, and current Incident_Status.
2. WHEN an operator requests a single Incident by Incident_ID, THE Backend_Service SHALL return that Incident including its current Incident_Status and its complete Timeline in chronological order.
3. IF an operator requests a single Incident by an Incident_ID that does not exist, THEN THE Backend_Service SHALL return a not-found error.
4. WHEN the Frontend_App displays an Incident, THE Frontend_App SHALL present the current Incident_Status and the Timeline_Events in chronological order.

### Requirement 3: Update Incident Status

**User Story:** As an operator, I want to advance an incident through valid lifecycle states, so that incident progress is accurately reflected and invalid states are prevented.

#### Acceptance Criteria

1. WHEN an operator requests a status change that is a Valid_Transition (OPEN -> INVESTIGATING or INVESTIGATING -> RESOLVED), THE Backend_Service SHALL update the Incident_Status to the requested state and persist the change through the Repository_Layer.
2. WHEN a Valid_Transition is applied, THE Backend_Service SHALL append a "status changed" Timeline_Event with a timestamp recording the previous and new Incident_Status.
3. IF an operator requests a status change that is not a Valid_Transition (for example OPEN -> RESOLVED or a backward change), THEN THE Backend_Service SHALL reject the request, leave the Incident_Status unchanged, and return a transition error.
4. IF an operator requests a status change to a value that is not one of OPEN, INVESTIGATING, or RESOLVED, THEN THE Backend_Service SHALL reject the request, leave the Incident_Status unchanged, and return a validation error.

### Requirement 4: Request AI Diagnosis

**User Story:** As an operator, I want to request an AI diagnosis for an incident, so that I receive an evidence-based analysis gathered from logs, metrics, history, and runbooks.

#### Acceptance Criteria

1. WHEN an operator requests a diagnosis for an existing Incident, THE Diagnosis_Agent SHALL gather evidence by invoking the MCP_Server tools get_recent_logs, get_service_metrics, get_incident_history, and search_runbook for the Incident service.
2. WHEN evidence has been gathered, THE Diagnosis_Agent SHALL call the LLM_Provider with the gathered evidence and produce a Diagnosis referencing that evidence.
3. WHEN a diagnosis is requested, THE Backend_Service SHALL append a "diagnosis requested" Timeline_Event with a timestamp to the Incident Timeline.
4. WHEN a Diagnosis is produced, THE Backend_Service SHALL persist the Diagnosis associated with the Incident through the Repository_Layer.
5. IF the LLM_Provider is unavailable or returns an error, THEN THE Diagnosis_Agent SHALL return a diagnosis-unavailable result and THE Backend_Service SHALL leave the Incident_Status unchanged.
6. WHERE a model identifier and endpoint are provided in configuration, THE Diagnosis_Agent SHALL use those configured values when calling the LLM_Provider.

### Requirement 5: Remediation Actions

**User Story:** As an operator, I want recommended remediation actions derived from the diagnosis, so that I know what steps to take to resolve the incident.

#### Acceptance Criteria

1. WHEN a Diagnosis is produced for an Incident, THE Diagnosis_Agent SHALL produce a set of Remediation_Actions derived from that Diagnosis.
2. WHEN Remediation_Actions are produced, THE Backend_Service SHALL append an "actions suggested" Timeline_Event with a timestamp to the Incident Timeline.
3. WHEN an operator requests the Remediation_Actions for an Incident, THE Backend_Service SHALL return the Remediation_Actions associated with that Incident.
4. WHEN the Frontend_App displays an Incident with Remediation_Actions, THE Frontend_App SHALL present each Remediation_Action.

### Requirement 6: Incident Timeline

**User Story:** As an operator, I want an append-only timeline of incident events with timestamps, so that I have an accurate audit history of what happened and when.

#### Acceptance Criteria

1. THE Backend_Service SHALL record Timeline_Events of type "created", "status changed", "diagnosis requested", and "actions suggested".
2. WHEN a Timeline_Event is recorded, THE Backend_Service SHALL store the event with a timestamp and append it to the Incident Timeline without modifying or removing existing Timeline_Events.
3. WHEN an operator retrieves an Incident Timeline, THE Backend_Service SHALL return the Timeline_Events ordered from earliest to latest by timestamp.

### Requirement 7: Testable Properties

**User Story:** As a developer, I want explicit, verifiable properties for identifiers and state transitions, so that these invariants can be validated with property-based tests.

#### Acceptance Criteria

1. THE Backend_Service SHALL ensure every Incident_ID is non-empty and matches the pattern `INC-\d{4,}`.
2. THE Backend_Service SHALL ensure every Incident_ID is unique across all persisted Incidents.
3. THE Backend_Service SHALL permit an Incident_Status change only when the change is a Valid_Transition (OPEN -> INVESTIGATING or INVESTIGATING -> RESOLVED).
4. IF a requested Incident_Status change is not a Valid_Transition, THEN THE Backend_Service SHALL preserve the existing Incident_Status.
