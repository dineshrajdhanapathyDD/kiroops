/**
 * Component tests for CreateIncidentPage (Task 13.6, Req 1.6/1.7).
 *
 * The services layer is mocked. These tests assert client-side rejection of a
 * whitespace-only title (no API call made) and surfacing of a server 422
 * validation error against the named field.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CreateIncidentPage } from "../pages/CreateIncidentPage";

vi.mock("../api/incidents", async () => {
  const actual =
    await vi.importActual<typeof import("../api/incidents")>(
      "../api/incidents",
    );
  return {
    ...actual,
    incidentsApi: {
      create: vi.fn(),
      list: vi.fn(),
      get: vi.fn(),
      updateStatus: vi.fn(),
      requestDiagnosis: vi.fn(),
      getRemediationActions: vi.fn(),
    },
  };
});

import { ApiError, incidentsApi } from "../api/incidents";

const mockedApi = vi.mocked(incidentsApi);

describe("CreateIncidentPage", () => {
  beforeEach(() => {
    mockedApi.create.mockReset();
  });

  it("rejects a whitespace-only title client-side without calling the API", async () => {
    const user = userEvent.setup();
    render(<CreateIncidentPage />);

    await user.type(screen.getByLabelText("Title"), "   ");
    await user.click(screen.getByRole("button", { name: /create incident/i }));

    expect(screen.getByText("Title is required.")).toBeInTheDocument();
    expect(mockedApi.create).not.toHaveBeenCalled();
  });

  it("surfaces a server 422 validation error on the named field", async () => {
    const user = userEvent.setup();
    mockedApi.create.mockRejectedValue(
      new ApiError("validation_error", "Title must be non-empty.", 422, "title"),
    );

    render(<CreateIncidentPage />);
    await user.type(screen.getByLabelText("Title"), "valid title");
    await user.click(screen.getByRole("button", { name: /create incident/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Title must be non-empty."),
      ).toBeInTheDocument(),
    );
  });

  it("calls the API with the selected severity and trimmed values on success", async () => {
    const user = userEvent.setup();
    mockedApi.create.mockResolvedValue({
      incidentId: "INC-0001",
      title: "DB connection errors",
      severity: "CRITICAL",
      service: "payments",
      status: "OPEN",
      createdAt: "2024-01-01T00:00:00+00:00",
    });

    const onCreated = vi.fn();
    render(<CreateIncidentPage onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Title"), "  DB connection errors  ");
    await user.selectOptions(screen.getByLabelText("Severity"), "CRITICAL");
    await user.type(screen.getByLabelText("Service"), "payments");
    await user.click(screen.getByRole("button", { name: /create incident/i }));

    await waitFor(() =>
      expect(mockedApi.create).toHaveBeenCalledWith({
        title: "DB connection errors",
        severity: "CRITICAL",
        service: "payments",
      }),
    );
    expect(onCreated).toHaveBeenCalledOnce();
  });
});
