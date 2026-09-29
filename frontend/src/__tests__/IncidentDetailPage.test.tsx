/**
 * Component tests for IncidentDetailPage (Task 13.6, Req 2.4 & 5.4).
 *
 * The services layer (`api/incidents`) is mocked so no network call is made.
 * These tests assert:
 *  - the current status is rendered (Req 2.2/2.4);
 *  - the timeline is rendered in chronological order as returned (Req 2.4);
 *  - after requesting a diagnosis, each remediation action is rendered (Req 5.4).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IncidentDetailPage } from "../pages/IncidentDetailPage";
import type { Diagnosis, IncidentDetail } from "../types";

// Mock the services layer so components never touch the network.
vi.mock("../api/incidents", async () => {
  const actual =
    await vi.importActual<typeof import("../api/incidents")>(
      "../api/incidents",
    );
  return {
    ...actual, // keep the real ApiError class for instanceof checks
    incidentsApi: {
      get: vi.fn(),
      requestDiagnosis: vi.fn(),
      updateStatus: vi.fn(),
      list: vi.fn(),
      create: vi.fn(),
      getRemediationActions: vi.fn(),
    },
  };
});

// Import after the mock so we get the mocked object.
import { incidentsApi } from "../api/incidents";

const mockedApi = vi.mocked(incidentsApi);

const detail: IncidentDetail = {
  incidentId: "INC-0001",
  title: "Checkout latency spike",
  severity: "HIGH",
  service: "checkout",
  status: "INVESTIGATING",
  createdAt: "2024-01-01T10:00:00+00:00",
  timeline: [
    {
      type: "created",
      timestamp: "2024-01-01T10:00:00+00:00",
      details: {},
    },
    {
      type: "status changed",
      timestamp: "2024-01-01T10:05:00+00:00",
      details: { from: "OPEN", to: "INVESTIGATING" },
    },
    {
      type: "diagnosis requested",
      timestamp: "2024-01-01T10:10:00+00:00",
      details: {},
    },
  ],
};

const diagnosis: Diagnosis = {
  incidentId: "INC-0001",
  summary: "Elevated error rate correlated with a recent deploy.",
  evidenceRefs: ["logs:checkout#123", "metrics:checkout#p95"],
  remediationActions: [
    {
      actionId: "ACT-1",
      description: "Roll back the latest deploy",
      rationale: "Error rate rose immediately after the deploy.",
    },
    {
      actionId: "ACT-2",
      description: "Scale out the checkout service",
      rationale: "p95 latency is above the SLO under current load.",
    },
  ],
};

describe("IncidentDetailPage", () => {
  beforeEach(() => {
    mockedApi.get.mockResolvedValue(detail);
    mockedApi.requestDiagnosis.mockResolvedValue(diagnosis);
  });

  it("renders the current status", async () => {
    render(<IncidentDetailPage incidentId="INC-0001" />);

    await waitFor(() =>
      expect(screen.getByTestId("current-status")).toHaveTextContent(
        "INVESTIGATING",
      ),
    );
  });

  it("renders the timeline in chronological order", async () => {
    render(<IncidentDetailPage incidentId="INC-0001" />);

    await waitFor(() => screen.getByRole("list", { name: "Timeline" }));

    const types = screen
      .getAllByTestId("timeline-type")
      .map((el) => el.textContent);

    expect(types).toEqual([
      "created",
      "status changed",
      "diagnosis requested",
    ]);
  });

  it("renders each remediation action after requesting a diagnosis", async () => {
    const user = userEvent.setup();
    render(<IncidentDetailPage incidentId="INC-0001" />);

    await waitFor(() => screen.getByTestId("current-status"));

    await user.click(screen.getByRole("button", { name: /request diagnosis/i }));

    await waitFor(() =>
      expect(mockedApi.requestDiagnosis).toHaveBeenCalledWith("INC-0001"),
    );

    const list = await screen.findByRole("list", {
      name: /remediation actions/i,
    });
    const items = within(list).getAllByTestId("remediation-action");
    expect(items).toHaveLength(2);

    expect(
      screen.getByText("Roll back the latest deploy"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Scale out the checkout service"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Error rate rose immediately after the deploy."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("p95 latency is above the SLO under current load."),
    ).toBeInTheDocument();

    // The diagnosis summary is also surfaced.
    expect(
      screen.getByText(
        "Elevated error rate correlated with a recent deploy.",
      ),
    ).toBeInTheDocument();
  });

  it("only offers valid next-state controls (INVESTIGATING -> RESOLVED)", async () => {
    render(<IncidentDetailPage incidentId="INC-0001" />);

    await waitFor(() => screen.getByTestId("current-status"));

    expect(
      screen.getByRole("button", { name: /move to resolved/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /move to open/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /move to investigating/i }),
    ).not.toBeInTheDocument();
  });
});
